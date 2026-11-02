"""
Module tải ảnh truyện tranh và Pixiv đa luồng (Downloader).
- Đối với truyện tranh: Tải từng chương thành một thư mục riêng (Chương 001, Chương 002...).
- Đối với Pixiv: Tải toàn bộ ảnh trực tiếp vào thư mục tác phẩm với độ phân giải gốc cao nhất.
"""

import os
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional
import httpx

from scraper import ChapterInfo, MangaInfo, sanitize_filename


class MangaDownloader:
    def __init__(
        self,
        output_dir: str = "downloads",
        max_workers: int = 6,
        timeout: float = 25.0,
        retries: int = 3,
        skip_existing: bool = True,
    ):
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.timeout = timeout
        self.retries = retries
        self.skip_existing = skip_existing
        self.is_cancelled = False

        self.client = httpx.Client(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
            follow_redirects=True,
            timeout=timeout,
        )

    def close(self):
        self.client.close()

    def cancel(self):
        """Kích hoạt huỷ tiến trình tải."""
        self.is_cancelled = True

    def _download_single_image(self, img_url: str, save_path: str, referer: str = "") -> bool:
        """Tải 1 ảnh với cơ chế retry tự động và chống chặn Referer."""
        if self.is_cancelled:
            return False

        # Nếu file đã tồn tại và có dung lượng hợp lệ (> 512 bytes)
        if self.skip_existing and os.path.exists(save_path) and os.path.getsize(save_path) > 512:
            return True

        # Đảm bảo Pixiv luôn có Referer hợp lệ (bắt buộc đối với máy chủ i.pximg.net)
        if "pximg.net" in img_url or "pixiv.net" in referer:
            referer = "https://www.pixiv.net/"

        headers = {}
        if referer:
            headers["Referer"] = referer

        for attempt in range(1, self.retries + 1):
            if self.is_cancelled:
                return False
            try:
                resp = self.client.get(img_url, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 0:
                    with open(save_path, "wb") as f:
                        f.write(resp.content)
                    return True
                elif resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(attempt * 1.5)
            except Exception:
                if attempt < self.retries:
                    time.sleep(attempt * 1.0)

        return False

    def _download_pixiv_image(self, img_url: str, fallback_url: Optional[str], save_path: str) -> bool:
        """Tải ảnh Pixiv: Ưu tiên ảnh gốc Original, nếu lỗi thì tự động tải ảnh Regular."""
        ok = self._download_single_image(img_url, save_path, referer="https://www.pixiv.net/")
        if ok:
            return True

        # Fallback ảnh nén regular nếu ảnh gốc bị lỗi hoặc 404
        if fallback_url and not self.is_cancelled:
            return self._download_single_image(fallback_url, save_path, referer="https://www.pixiv.net/")

        return False

    def download_chapter(
        self,
        chapter: ChapterInfo,
        image_urls: List[str],
        manga_dir: str,
        chap_index: int,
        total_chaps: int,
        on_progress: Optional[Callable[[int, int, int, int, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> int:
        """
        Tải toàn bộ ảnh của 1 chương vào một thư mục riêng:
        manga_dir / chapter.display_name / 001.jpg, 002.jpg...
        """
        if self.is_cancelled:
            return 0

        clean_chap_name = sanitize_filename(chapter.display_name)
        chap_dir = os.path.join(manga_dir, clean_chap_name)
        os.makedirs(chap_dir, exist_ok=True)

        total_images = len(image_urls)
        if total_images == 0:
            if on_log:
                on_log(f"⚠️ {chapter.display_name}: Không tìm thấy ảnh nào.")
            return 0

        # Kiểm tra nếu chương đã được tải đầy đủ trước đó
        if self.skip_existing:
            existing_valid_files = [
                f for f in os.listdir(chap_dir)
                if os.path.isfile(os.path.join(chap_dir, f)) and os.path.getsize(os.path.join(chap_dir, f)) > 512
            ]
            if len(existing_valid_files) >= total_images:
                if on_log:
                    on_log(f"⏩ {chapter.display_name}: Đã tải đủ {total_images} ảnh, bỏ qua.")
                if on_progress:
                    on_progress(chap_index, total_chaps, total_images, total_images, "Đã có sẵn")
                return total_images

        if on_log:
            on_log(f"📥 Đang tải {chapter.display_name} ({total_images} ảnh)...")

        pad_width = 3 if total_images < 1000 else 4
        success_count = 0

        # Chuẩn bị danh sách tác vụ tải ảnh
        tasks = []
        for i, url in enumerate(image_urls, start=1):
            parsed_path = urllib.parse.urlparse(url).path
            ext = os.path.splitext(parsed_path)[1].lower()
            if not ext or len(ext) > 5 or ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                ext = ".jpg"

            filename = f"{i:0{pad_width}d}{ext}"
            file_path = os.path.join(chap_dir, filename)
            tasks.append((url, file_path, i, filename))

        # Tải đa luồng
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._download_single_image, url, path, chapter.url): (i, fname)
                for url, path, i, fname in tasks
            }

            for future in as_completed(future_to_task):
                if self.is_cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                i, fname = future_to_task[future]
                try:
                    ok = future.result()
                    if ok:
                        success_count += 1
                except Exception as ex:
                    if on_log:
                        on_log(f"❌ Lỗi tải ảnh {fname}: {ex}")

                if on_progress:
                    on_progress(chap_index, total_chaps, success_count, total_images, fname)

        if on_log and not self.is_cancelled:
            on_log(f"✅ Hoàn thành {chapter.display_name} ({success_count}/{total_images} ảnh).")

        return success_count

    def _download_single_post(
        self,
        manga: MangaInfo,
        selected_items: List[ChapterInfo],
        on_progress: Optional[Callable[[int, int, int, int, str], None]] = None,
        on_all_complete: Optional[Callable[[int, int, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> int:
        """
        Tải toàn bộ hoặc các ảnh được chọn của một bài viết đơn lẻ (Pixiv).
        Tất cả ảnh được lưu trực tiếp vào thư mục bài viết (không lồng thêm thư mục chương).
        """
        self.is_cancelled = False
        post_dir = os.path.join(self.output_dir, sanitize_filename(manga.title))
        os.makedirs(post_dir, exist_ok=True)

        total_images = len(selected_items)
        if total_images == 0:
            if on_log:
                on_log("⚠️ Không có ảnh nào được chọn để tải.")
            return 0

        if on_log:
            on_log(f"📂 Thư mục lưu bài viết: {os.path.abspath(post_dir)}")
            on_log(f"🚀 Bắt đầu tải {total_images} ảnh từ Pixiv...")

        pad_width = 3 if total_images < 1000 else 4
        tasks = []
        for item in selected_items:
            num = int(item.chapter_num)
            parsed_path = urllib.parse.urlparse(item.url).path
            ext = os.path.splitext(parsed_path)[1].lower()
            if not ext or len(ext) > 5 or ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                ext = ".png"

            filename = f"{num:0{pad_width}d}{ext}"
            file_path = os.path.join(post_dir, filename)
            tasks.append((item.url, item.fallback_url, file_path, num, filename))

        success_count = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._download_pixiv_image, url, fallback, path): (num, fname)
                for url, fallback, path, num, fname in tasks
            }

            for future in as_completed(future_to_task):
                if self.is_cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                num, fname = future_to_task[future]
                try:
                    ok = future.result()
                    if ok:
                        success_count += 1
                except Exception as ex:
                    if on_log:
                        on_log(f"❌ Lỗi tải ảnh {fname}: {ex}")

                if on_progress:
                    on_progress(1, 1, success_count, total_images, fname)

        if on_all_complete:
            on_all_complete(1, success_count, post_dir)

        if on_log and not self.is_cancelled:
            on_log(
                f"🎉 TẤT CẢ ĐÃ HOÀN THÀNH! Đã lưu {success_count}/{total_images} ảnh Pixiv tại:\n👉 {os.path.abspath(post_dir)}"
            )

        return success_count

    def download_manga(
        self,
        manga: MangaInfo,
        chapters_to_download: List[ChapterInfo],
        fetch_images_func: Callable[[str], List[str]],
        on_chapter_start: Optional[Callable[[int, int, ChapterInfo], None]] = None,
        on_progress: Optional[Callable[[int, int, int, int, str], None]] = None,
        on_chapter_complete: Optional[Callable[[int, int, ChapterInfo, int], None]] = None,
        on_all_complete: Optional[Callable[[int, int, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        """
        Tải danh sách các chương của truyện tranh hoặc các ảnh của Pixiv.
        """
        self.is_cancelled = False

        # Nếu là bài viết Pixiv
        if manga.is_single_post:
            return self._download_single_post(
                manga=manga,
                selected_items=chapters_to_download,
                on_progress=on_progress,
                on_all_complete=on_all_complete,
                on_log=on_log,
            )

        # Nếu là truyện tranh thông thường (TruyenQQ...)
        manga_dir = os.path.join(self.output_dir, sanitize_filename(manga.title))
        os.makedirs(manga_dir, exist_ok=True)

        total_chaps = len(chapters_to_download)
        if on_log:
            on_log(f"📂 Thư mục lưu truyện: {os.path.abspath(manga_dir)}")
            on_log(f"🚀 Bắt đầu tải {total_chaps} chương...")

        total_downloaded_images = 0

        for idx, chapter in enumerate(chapters_to_download, start=1):
            if self.is_cancelled:
                if on_log:
                    on_log("⏹️ Đã dừng tiến trình tải theo yêu cầu.")
                break

            if on_chapter_start:
                on_chapter_start(idx, total_chaps, chapter)

            # Lấy link ảnh của chương
            try:
                images = fetch_images_func(chapter.url)
            except Exception as e:
                if on_log:
                    on_log(f"❌ Không thể lấy danh sách ảnh của {chapter.display_name}: {e}")
                continue

            # Tải chương vào thư mục riêng
            img_count = self.download_chapter(
                chapter=chapter,
                image_urls=images,
                manga_dir=manga_dir,
                chap_index=idx,
                total_chaps=total_chaps,
                on_progress=on_progress,
                on_log=on_log,
            )
            total_downloaded_images += img_count

            if on_chapter_complete:
                on_chapter_complete(idx, total_chaps, chapter, img_count)

            # Nghỉ ngắn giữa các chương để tránh bị chặn IP
            if not self.is_cancelled and idx < total_chaps:
                time.sleep(0.3)

        if on_all_complete:
            on_all_complete(total_chaps, total_downloaded_images, manga_dir)

        if on_log and not self.is_cancelled:
            on_log(f"🎉 TẤT CẢ ĐÃ HOÀN THÀNH! Tổng cộng {total_downloaded_images} ảnh đã được lưu tại:\n👉 {os.path.abspath(manga_dir)}")
