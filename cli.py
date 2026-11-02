"""
Giao diện dòng lệnh (CLI) tải truyện tranh và Pixiv đa luồng.
Chạy trực tiếp: python cli.py hoặc truyền tham số.
"""

import argparse
import os
import re
import sys
from typing import List

# Đảm bảo console Windows hiển thị đúng UTF-8 (tiếng Việt, tiếng Nhật, icon)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import get_pixiv_cookie
from downloader import MangaDownloader
from scraper import ChapterInfo, MangaInfo, MangaScraper, extract_pixiv_id


def print_banner():
    banner = """
============================================================
      TOOL LEECH TRUYỆN TRANH & PIXIV DOWNLOADER           
      - Tải truyện theo từng chương (Chương 001, 002...)   
      - Tải trọn bộ ảnh Pixiv độ phân giải gốc cao nhất     
============================================================
"""
    print(banner)


def parse_custom_selection(selection_str: str, chapters: List[ChapterInfo]) -> List[ChapterInfo]:
    """
    Phân tích chuỗi lựa chọn chương/ảnh, hỗ trợ:
    - Khoảng: 1-5, 10-20
    - Số cụ thể: 1, 3, 5, 7
    - Kết hợp: 1-5, 8, 11-15
    """
    selected_dict = {}
    parts = [p.strip() for p in selection_str.split(",") if p.strip()]

    # Tạo map từ số thứ tự sang đối tượng chapter
    chap_map = {}
    for c in chapters:
        chap_map[c.chapter_num] = c

    for part in parts:
        if "-" in part:
            bounds = part.split("-")
            try:
                start = float(bounds[0].strip())
                end = float(bounds[1].strip())
                if start > end:
                    start, end = end, start
                for c in chapters:
                    if start <= c.chapter_num <= end:
                        selected_dict[c.url] = c
            except ValueError:
                print(f"⚠️ Bỏ qua phần không hợp lệ: {part}")
        else:
            try:
                num = float(part)
                if num in chap_map:
                    matched_chap = chap_map[num]
                    selected_dict[matched_chap.url] = matched_chap
                else:
                    matched = [c for c in chapters if abs(c.chapter_num - num) < 0.01]
                    if matched:
                        selected_dict[matched[0].url] = matched[0]
                    else:
                        print(f"⚠️ Không tìm thấy mục số {num}")
            except ValueError:
                print(f"⚠️ Bỏ qua phần không hợp lệ: {part}")

    # Sắp xếp lại theo thứ tự
    result = sorted(list(selected_dict.values()), key=lambda c: c.chapter_num)
    return result


def progress_callback(chap_idx: int, total_chaps: int, img_idx: int, total_imgs: int, filename: str):
    """Hiển thị thanh tiến trình trực quan trên terminal cho truyện tranh."""
    bar_len = 25
    if total_imgs > 0:
        percent = img_idx / total_imgs
        filled = int(bar_len * percent)
        bar = "█" * filled + "░" * (bar_len - filled)
        pct_text = f"{percent * 100:5.1f}%"
    else:
        bar = "░" * bar_len
        pct_text = "  0.0%"

    sys.stdout.write(
        f"\r[{bar}] {pct_text} | Chap {chap_idx}/{total_chaps} | Ảnh: {img_idx}/{total_imgs} ({filename})   "
    )
    sys.stdout.flush()
    if img_idx == total_imgs and total_imgs > 0:
        print()


def progress_callback_pixiv(chap_idx: int, total_chaps: int, img_idx: int, total_imgs: int, filename: str):
    """Hiển thị thanh tiến trình trực quan trên terminal cho Pixiv."""
    bar_len = 25
    if total_imgs > 0:
        percent = img_idx / total_imgs
        filled = int(bar_len * percent)
        bar = "█" * filled + "░" * (bar_len - filled)
        pct_text = f"{percent * 100:5.1f}%"
    else:
        bar = "░" * bar_len
        pct_text = "  0.0%"

    sys.stdout.write(
        f"\r[{bar}] {pct_text} | Đang tải ảnh: {img_idx}/{total_imgs} ({filename})   "
    )
    sys.stdout.flush()
    if img_idx == total_imgs and total_imgs > 0:
        print()


def main():
    parser = argparse.ArgumentParser(description="Tool tải truyện tranh và ảnh Pixiv theo thư mục")
    parser.add_argument("url", nargs="?", help="Link truyện hoặc link Pixiv (ví dụ: https://www.pixiv.net/en/artworks/47385304)")
    parser.add_argument("--all", action="store_true", help="Tải tất cả các chương hoặc toàn bộ ảnh trong bài Pixiv")
    parser.add_argument("--range", help="Khoảng chương/ảnh cần tải (ví dụ: 1-10 hoặc 1,3,5-10)")
    parser.add_argument("--latest", type=int, help="Chỉ tải N chương/ảnh mới nhất")
    parser.add_argument("--threads", type=int, default=6, help="Số luồng tải ảnh song song (mặc định 6)")
    parser.add_argument("--output", default="downloads", help="Thư mục lưu (mặc định: downloads)")
    parser.add_argument("--force", action="store_true", help="Tải lại ngay cả khi ảnh đã có sẵn")
    parser.add_argument("--cookie", help="Pixiv PHPSESSID cookie (dành cho bài R-18 hoặc yêu cầu đăng nhập)")

    args = parser.parse_args()

    print_banner()

    url = args.url
    if not url:
        print("💡 Hãy dán link truyện tranh hoặc link bài viết Pixiv bạn muốn tải.")
        print("   Ví dụ truyện tranh: https://truyenqq.com.co/truyen/shishunki-renaissance-david-kun")
        print("   Ví dụ Pixiv      : https://www.pixiv.net/en/artworks/47385304")
        try:
            url = input("\n👉 Nhập link: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nĐã hủy.")
            return

    if not url:
        print("❌ Bạn chưa nhập link. Kết thúc.")
        return

    is_pixiv = bool(extract_pixiv_id(url))
    cookie = args.cookie or get_pixiv_cookie()

    print(f"\n🔍 Đang kết nối và lấy thông tin từ: {url} ...")
    try:
        scraper = MangaScraper(pixiv_cookie=cookie)
        manga = scraper.fetch_manga_info(url)
    except Exception as e:
        print(f"❌ Lỗi khi lấy thông tin: {e}")
        return

    print("=" * 60)
    if manga.is_single_post:
        print(f"📖 Tác phẩm Pixiv : {manga.title}")
        print(f"✍️ Tác giả (Artist): {manga.author}")
        print(f"📌 Thể loại       : {manga.status}")
        print(f"🖼️ Tổng số ảnh    : {manga.total_chapters} ảnh")
        if manga.chapters:
            print(f"🔹 Ảnh đầu        : {manga.chapters[0].display_name}")
            print(f"🔹 Ảnh cuối       : {manga.chapters[-1].display_name}")
    else:
        print(f"📖 Tên truyện   : {manga.title}")
        print(f"✍️ Tác giả     : {manga.author}")
        print(f"📌 Tình trạng   : {manga.status}")
        print(f"📚 Tổng số chap : {manga.total_chapters} chương")
        if manga.chapters:
            print(f"🔹 Chương đầu   : {manga.chapters[0].display_name}")
            print(f"🔹 Chương cuối  : {manga.chapters[-1].display_name}")
    print("=" * 60)

    if not manga.chapters:
        print("❌ Không tìm thấy nội dung ảnh nào để tải.")
        return

    # Xác định các chương hoặc ảnh cần tải
    items_to_download: List[ChapterInfo] = []

    if args.all:
        items_to_download = manga.chapters
    elif args.range:
        items_to_download = parse_custom_selection(args.range, manga.chapters)
    elif args.latest:
        n = min(args.latest, len(manga.chapters))
        items_to_download = manga.chapters[-n:]
    else:
        # Chế độ tương tác hỏi người dùng
        if manga.is_single_post:
            print("\nChọn tùy chọn tải ảnh Pixiv:")
            print(f"  [1] Tải TOÀN BỘ {manga.total_chapters} ảnh trong bài này (Mặc định)")
            print("  [2] Tải theo khoảng ảnh (ví dụ: 1-10)")
            print("  [3] Tải các ảnh cụ thể (ví dụ: 1, 3, 5, 8-12)")
            print("  [4] Chỉ tải N ảnh mới/cuối")

            choice = input("\n👉 Nhập lựa chọn [1-4] (bấm Enter để chọn 1 - Tải toàn bộ): ").strip()
            if choice in ("", "1"):
                items_to_download = manga.chapters
            elif choice == "2":
                val = input("👉 Nhập khoảng ảnh (ví dụ: 1-10): ").strip()
                items_to_download = parse_custom_selection(val, manga.chapters)
            elif choice == "3":
                val = input("👉 Nhập danh sách ảnh (ví dụ: 1, 3, 5, 8-12): ").strip()
                items_to_download = parse_custom_selection(val, manga.chapters)
            elif choice == "4":
                num_str = input("👉 Bạn muốn tải bao nhiêu ảnh cuối? ").strip()
                try:
                    n = int(num_str)
                    n = min(max(1, n), len(manga.chapters))
                    items_to_download = manga.chapters[-n:]
                except ValueError:
                    print("⚠️ Giá trị không hợp lệ, tải toàn bộ.")
                    items_to_download = manga.chapters
            else:
                print("Lựa chọn không hợp lệ, tải toàn bộ.")
                items_to_download = manga.chapters
        else:
            print("\nChọn chế độ tải truyện tranh:")
            print("  [1] Tải TOÀN BỘ các chương (Mặc định)")
            print("  [2] Tải theo khoảng chương (ví dụ: 1-10)")
            print("  [3] Tải các chương cụ thể (ví dụ: 1, 3, 5, 8-12)")
            print("  [4] Chỉ tải N chương mới nhất")

            choice = input("\n👉 Nhập lựa chọn [1-4] (bấm Enter để chọn 1): ").strip()
            if choice in ("", "1"):
                items_to_download = manga.chapters
            elif choice == "2":
                val = input("👉 Nhập khoảng chương (ví dụ: 1-10): ").strip()
                items_to_download = parse_custom_selection(val, manga.chapters)
            elif choice == "3":
                val = input("👉 Nhập danh sách chương (ví dụ: 1, 3, 5, 8-12): ").strip()
                items_to_download = parse_custom_selection(val, manga.chapters)
            elif choice == "4":
                num_str = input("👉 Bạn muốn tải bao nhiêu chương mới nhất? ").strip()
                try:
                    n = int(num_str)
                    n = min(max(1, n), len(manga.chapters))
                    items_to_download = manga.chapters[-n:]
                except ValueError:
                    print("⚠️ Giá trị không hợp lệ, tải toàn bộ.")
                    items_to_download = manga.chapters
            else:
                print("Lựa chọn không hợp lệ, tải toàn bộ.")
                items_to_download = manga.chapters

    if not items_to_download:
        print("❌ Không có mục nào được chọn để tải.")
        return

    unit_name = "ảnh" if manga.is_single_post else "chương"
    print(f"\n🚀 Sẽ tải {len(items_to_download)} {unit_name}.")
    print(f"⚡ Số luồng tải song song: {args.threads}")
    print(f"📁 Thư mục lưu          : {os.path.abspath(args.output)}\\{manga.title}\\")
    print("-" * 60)

    downloader = MangaDownloader(
        output_dir=args.output,
        max_workers=args.threads,
        skip_existing=not args.force,
    )

    cb = progress_callback_pixiv if manga.is_single_post else progress_callback

    try:
        downloader.download_manga(
            manga=manga,
            chapters_to_download=items_to_download,
            fetch_images_func=scraper.fetch_chapter_images,
            on_progress=cb,
            on_log=print,
        )
    except KeyboardInterrupt:
        print("\n\n⏹️ Đã nhận phím Ctrl+C, đang dừng...")
        downloader.cancel()
    finally:
        scraper.close()
        downloader.close()

    target_dir = os.path.join(args.output, manga.title)
    if os.path.exists(target_dir):
        print("\n" + "=" * 60)
        print(f"📂 Thư mục đã tải: {os.path.abspath(target_dir)}")
        if sys.platform == "win32":
            try:
                open_folder = input("👉 Bạn có muốn mở thư mục ngay bây giờ? (y/n, mặc định y): ").strip().lower()
                if open_folder in ("", "y", "yes"):
                    os.startfile(os.path.abspath(target_dir))
            except Exception:
                pass


if __name__ == "__main__":
    main()
