"""
Module cào dữ liệu truyện tranh và tác phẩm Pixiv (Manga & Pixiv Scraper).
Hỗ trợ TruyenQQ (truyenqq.com.co, truyenqqviet, truyenqqno,...), các trang truyện phổ biến và Pixiv (pixiv.net).
"""

import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional, Tuple
import httpx
from bs4 import BeautifulSoup

from config import get_pixiv_cookie

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,ja-JP;q=0.8,ja;q=0.7,en-US;q=0.6,en;q=0.5",
}


@dataclass
class ChapterInfo:
    title: str
    url: str
    chapter_num: float
    display_name: str
    fallback_url: Optional[str] = None


@dataclass
class MangaInfo:
    title: str
    url: str
    cover_url: Optional[str]
    total_chapters: int
    chapters: List[ChapterInfo]
    author: str = "Không rõ"
    status: str = "Đang cập nhật"
    is_single_post: bool = False
    illust_id: Optional[str] = None


def sanitize_filename(name: str) -> str:
    """Loại bỏ ký tự cấm trong tên file/thư mục trên Windows."""
    # Các ký tự cấm trên Windows: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "Unnamed"


def is_pixiv_url(url: str) -> bool:
    """Kiểm tra xem link có thuộc Pixiv không."""
    lower = url.lower()
    return "pixiv.net" in lower or "pximg.net" in lower


def extract_pixiv_id(url: str) -> Optional[str]:
    """Trích xuất ID tác phẩm Pixiv (illust_id) từ URL hoặc chuỗi nhập vào."""
    clean = url.strip()
    # 1. Định dạng: https://www.pixiv.net/en/artworks/47385304 hoặc /artworks/47385304
    m = re.search(r"artworks/(\d+)", clean)
    if m:
        return m.group(1)

    # 2. Định dạng: illust_id=47385304
    m = re.search(r"[?&]illust_id=(\d+)", clean)
    if m:
        return m.group(1)

    # 3. Định dạng rút gọn: pixiv.net/i/47385304
    m = re.search(r"/i/(\d+)", clean)
    if m:
        return m.group(1)

    # 4. Người dùng nhập trực tiếp ID là dãy số nguyên (từ 5 chữ số trở lên)
    if clean.isdigit() and len(clean) >= 5:
        return clean

    return None


def extract_chapter_number(title: str, url: str = "") -> float:
    """Trích xuất số thứ tự chương từ tiêu đề hoặc link."""
    # Ưu tiên tìm trong title: "Chương 1", "Chap 10.5", "Chương 24"
    match = re.search(r"(?:chương|chap|ch\.?|episode|tập)\s*(\d+(?:\.\d+)?)", title, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    # Nếu không thấy, tìm số trong url: /chapter-1, /chap-2.5
    match_url = re.search(r"[-_](?:chapter|chap|ch)[-_](\d+(?:\.\d+)?)", url, re.IGNORECASE)
    if match_url:
        try:
            return float(match_url.group(1))
        except ValueError:
            pass

    # Tìm số bất kỳ đầu tiên trong title
    match_any = re.search(r"(\d+(?:\.\d+)?)", title)
    if match_any:
        try:
            return float(match_any.group(1))
        except ValueError:
            pass

    return 0.0


class MangaScraper:
    def __init__(self, timeout: float = 25.0, pixiv_cookie: Optional[str] = None):
        self.timeout = timeout
        self.pixiv_cookie = (pixiv_cookie if pixiv_cookie is not None else get_pixiv_cookie()).strip()

        client_headers = dict(HEADERS)
        if self.pixiv_cookie:
            cookie_val = self.pixiv_cookie if "PHPSESSID=" in self.pixiv_cookie else f"PHPSESSID={self.pixiv_cookie}"
            client_headers["Cookie"] = cookie_val

        self.client = httpx.Client(
            headers=client_headers,
            follow_redirects=True,
            timeout=timeout,
            verify=True,
        )

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def normalize_url(self, url: str) -> str:
        """Chuẩn hóa URL truyện hoặc bài viết Pixiv."""
        url = url.strip()

        # Kiểm tra nếu là Pixiv
        pixiv_id = extract_pixiv_id(url)
        if pixiv_id:
            return f"https://www.pixiv.net/artworks/{pixiv_id}"

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        # Nếu là link chap truyenqq (ví dụ /truyen/ten-truyen-chapter-1)
        truyenqq_chap_match = re.search(r"^(https?://[^/]+/truyen/[^/]+)-chapter-\d+.*$", url)
        if truyenqq_chap_match:
            return truyenqq_chap_match.group(1)

        return url

    def fetch_pixiv_info(self, illust_id: str, original_url: str) -> MangaInfo:
        """
        Lấy thông tin chi tiết bài viết và danh sách toàn bộ các ảnh từ Pixiv AJAX API.
        Không cần Selenium hay trình duyệt ngoài.
        """
        ajax_illust_url = f"https://www.pixiv.net/ajax/illust/{illust_id}"
        ajax_pages_url = f"https://www.pixiv.net/ajax/illust/{illust_id}/pages"

        pixiv_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Referer": "https://www.pixiv.net/",
            "Accept": "application/json",
        }
        if self.pixiv_cookie:
            cookie_val = self.pixiv_cookie if "PHPSESSID=" in self.pixiv_cookie else f"PHPSESSID={self.pixiv_cookie}"
            pixiv_headers["Cookie"] = cookie_val

        # 1. Lấy thông tin bài viết (Tiêu đề, tác giả, số trang...)
        try:
            resp_illust = self.client.get(ajax_illust_url, headers=pixiv_headers)
        except Exception as e:
            raise ConnectionError(f"Không thể kết nối đến máy chủ Pixiv: {e}")

        if resp_illust.status_code in (403, 404):
            if not self.pixiv_cookie:
                raise ValueError(
                    f"Không thể truy cập tác phẩm Pixiv ID {illust_id} (Mã lỗi HTTP {resp_illust.status_code}).\n"
                    "Nếu bài viết này thuộc thể loại R-18 hoặc yêu cầu đăng nhập, "
                    "vui lòng cài đặt Pixiv Cookie (PHPSESSID) để tải."
                )
            raise ValueError(
                f"Không tìm thấy tác phẩm Pixiv ID {illust_id} hoặc Cookie đã hết hạn (HTTP {resp_illust.status_code})."
            )

        illust_json = resp_illust.json()
        if illust_json.get("error"):
            msg = illust_json.get("message", "Lỗi không xác định từ Pixiv")
            if not self.pixiv_cookie:
                raise ValueError(
                    f"Pixiv thông báo: {msg}.\n"
                    "Nếu đây là bài viết R-18 hoặc bị giới hạn độ tuổi, vui lòng nhập Pixiv Cookie (PHPSESSID)."
                )
            raise ValueError(f"Pixiv thông báo: {msg}")

        body = illust_json.get("body", {})
        title = body.get("illustTitle") or body.get("title") or f"Pixiv_{illust_id}"
        author = body.get("userName") or "Không rõ"
        page_count = body.get("pageCount", 1)

        # Thumbnail xem trước
        cover_url = None
        urls_obj = body.get("urls", {})
        if urls_obj:
            cover_url = urls_obj.get("regular") or urls_obj.get("small") or urls_obj.get("thumb_mini")

        # 2. Lấy danh sách link ảnh đầy đủ của các trang
        try:
            resp_pages = self.client.get(ajax_pages_url, headers=pixiv_headers)
            resp_pages.raise_for_status()
            pages_json = resp_pages.json()
            pages_data = pages_json.get("body", [])
        except Exception:
            pages_data = []

        # Nếu endpoint pages rỗng (thường gặp ở bài chỉ có 1 ảnh duy nhất)
        if not pages_data and urls_obj.get("original"):
            pages_data = [{"urls": urls_obj}]

        raw_chapters: List[ChapterInfo] = []
        pad_width = 2 if len(pages_data) < 100 else 3

        for idx, page in enumerate(pages_data, start=1):
            p_urls = page.get("urls", {})
            orig_img = p_urls.get("original") or p_urls.get("regular")
            fallback_img = p_urls.get("regular") or p_urls.get("small")
            if not orig_img:
                continue

            display_name = f"Ảnh {idx:0{pad_width}d}"
            raw_chapters.append(
                ChapterInfo(
                    title=f"Ảnh {idx}",
                    url=orig_img,
                    chapter_num=float(idx),
                    display_name=display_name,
                    fallback_url=fallback_img,
                )
            )

        clean_title = sanitize_filename(title)[:80].strip()
        formatted_title = f"[Pixiv] {illust_id} - {clean_title}"

        return MangaInfo(
            title=formatted_title,
            url=f"https://www.pixiv.net/artworks/{illust_id}",
            cover_url=cover_url,
            total_chapters=len(raw_chapters),
            chapters=raw_chapters,
            author=author,
            status=f"Pixiv Artwork ({len(raw_chapters)} ảnh)",
            is_single_post=True,
            illust_id=illust_id,
        )

    def fetch_manga_info(self, url: str) -> MangaInfo:
        """Lấy thông tin truyện tranh hoặc tác phẩm Pixiv."""
        # 1. Xử lý nếu là link Pixiv
        pixiv_id = extract_pixiv_id(url)
        if pixiv_id:
            return self.fetch_pixiv_info(pixiv_id, url)

        # 2. Xử lý các trang truyện tranh (TruyenQQ, NetTruyen...)
        normalized_url = self.normalize_url(url)
        resp = self.client.get(normalized_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Tên truyện
        title_tag = (
            soup.select_one("h1[itemprop='name']")
            or soup.select_one("h1.title-detail")
            or soup.select_one("h1")
        )
        title = title_tag.get_text(strip=True) if title_tag else "Truyện Tranh"

        # Ảnh bìa
        cover_tag = (
            soup.select_one(".book_avatar img")
            or soup.select_one(".col-image img")
            or soup.select_one("meta[property='og:image']")
        )
        cover_url = None
        if cover_tag:
            if cover_tag.name == "meta":
                cover_url = cover_tag.get("content")
            else:
                cover_url = cover_tag.get("src") or cover_tag.get("data-src")
            if cover_url and not cover_url.startswith("http"):
                cover_url = urllib.parse.urljoin(normalized_url, cover_url)

        # Tác giả & Tình trạng
        author = "Không rõ"
        status = "Đang cập nhật"
        author_li = soup.select_one(".author .org, .author a, .col-xs-9 a.org")
        if author_li:
            author = author_li.get_text(strip=True)

        status_li = soup.select_one(".status .col-xs-9, li.status p.col-xs-9")
        if status_li:
            status = status_li.get_text(strip=True)

        # Danh sách chương
        chapter_elements = soup.select(".works-chapter-item .name-chap a")
        if not chapter_elements:
            chapter_elements = soup.select(".list-chapter nav ul li .chapter a")
        if not chapter_elements:
            chapter_elements = [
                a for a in soup.find_all("a", href=True)
                if re.search(r"(?:chapter|chuong)-\d+", a["href"], re.I)
            ]

        raw_chapters: List[ChapterInfo] = []
        seen_urls = set()

        for a in chapter_elements:
            chap_url = a["href"].strip()
            if not chap_url.startswith("http"):
                chap_url = urllib.parse.urljoin(normalized_url, chap_url)

            if chap_url in seen_urls:
                continue
            seen_urls.add(chap_url)

            chap_title = a.get_text(strip=True)
            if not chap_title:
                chap_title = a.get("title", "").strip() or "Chương"

            chap_num = extract_chapter_number(chap_title, chap_url)

            display_name = chap_title
            raw_chapters.append(
                ChapterInfo(
                    title=chap_title,
                    url=chap_url,
                    chapter_num=chap_num,
                    display_name=display_name,
                )
            )

        # Sắp xếp chương từ đầu đến cuối (Chương 1 -> Chương mới nhất)
        if raw_chapters:
            if len(raw_chapters) > 1 and raw_chapters[0].chapter_num > raw_chapters[-1].chapter_num:
                raw_chapters.reverse()
            else:
                raw_chapters.sort(key=lambda c: c.chapter_num)

        # Chuẩn hóa display_name có số thứ tự đều nhau
        max_num = int(raw_chapters[-1].chapter_num) if raw_chapters else 0
        pad_width = 3 if max_num < 1000 else 4

        for chap in raw_chapters:
            if chap.chapter_num.is_integer():
                formatted_num = f"{int(chap.chapter_num):0{pad_width}d}"
            else:
                formatted_num = f"{chap.chapter_num:0{pad_width+2}.1f}"

            chap.display_name = f"Chương {formatted_num}"

        return MangaInfo(
            title=sanitize_filename(title),
            url=normalized_url,
            cover_url=cover_url,
            total_chapters=len(raw_chapters),
            chapters=raw_chapters,
            author=author,
            status=status,
            is_single_post=False,
        )

    def fetch_chapter_images(self, chapter_url: str) -> List[str]:
        """Lấy danh sách link ảnh của 1 chương hoặc bài viết."""
        # 1. Nếu chapter_url đã là link ảnh trực tiếp
        lower = chapter_url.lower()
        if any(lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]) or "pximg.net" in lower:
            return [chapter_url]

        # 2. Nếu là link Pixiv
        pixiv_id = extract_pixiv_id(chapter_url)
        if pixiv_id:
            info = self.fetch_pixiv_info(pixiv_id, chapter_url)
            return [c.url for c in info.chapters]

        # 3. Quét ảnh từ web truyện tranh
        resp = self.client.get(chapter_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        selectors = [
            ".chapter-images img",
            ".page-chapter img",
            ".chapter_content img",
            ".reading-detail .page-chapter img",
            ".box_doc img",
            "#chapter_content img",
        ]

        img_tags = []
        for sel in selectors:
            found = soup.select(sel)
            if found:
                img_tags = found
                break

        if not img_tags:
            img_tags = soup.find_all("img", class_=lambda c: c and "chapter-img" in c)

        image_urls: List[str] = []
        seen = set()

        for img in img_tags:
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or img.get("data-cdn")
            )
            if not src:
                continue

            src = src.strip()
            if not src.startswith("http"):
                src = urllib.parse.urljoin(chapter_url, src)

            if any(bad in src.lower() for bad in ["logo", "icon", "banner", "advert"]):
                continue

            if src not in seen:
                seen.add(src)
                image_urls.append(src)

        return image_urls
