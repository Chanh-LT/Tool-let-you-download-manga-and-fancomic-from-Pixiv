"""
Giao diện đồ họa (GUI) cho Tool Leech Truyện Tranh & Tải Ảnh Pixiv.
Được viết bằng Tkinter - trực quan, nhẹ, dùng ngay không cần cài đặt thêm server.
"""

import io
import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import List, Optional
import httpx
from PIL import Image, ImageTk

from config import get_pixiv_cookie, set_pixiv_cookie
from downloader import MangaDownloader
from scraper import ChapterInfo, MangaInfo, MangaScraper, sanitize_filename


class MangaDownloaderGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Manga & Pixiv Downloader - Tool Tải Truyện & Pixiv")
        self.root.geometry("860x780")
        self.root.minsize(740, 660)

        # Cấu hình màu sắc & font phong cách hiện đại, thanh lịch
        self.bg_color = "#f8f9fa"
        self.card_bg = "#ffffff"
        self.primary_color = "#2563eb"  # Xanh dương hiện đại
        self.accent_color = "#16a34a"   # Xanh lá hoàn thành
        self.text_color = "#1f2937"
        self.font_main = ("Segoe UI", 10)
        self.font_bold = ("Segoe UI", 10, "bold")
        self.font_title = ("Segoe UI", 13, "bold")

        self.root.configure(bg=self.bg_color)

        # Biến trạng thái
        self.manga_info: Optional[MangaInfo] = None
        self.downloader: Optional[MangaDownloader] = None
        self.download_thread: Optional[threading.Thread] = None
        self.log_queue = queue.Queue()
        self.cover_img_tk = None

        self._setup_style()
        self._build_ui()
        self._check_queue()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TLabel", background=self.bg_color, foreground=self.text_color, font=self.font_main)
        style.configure("Card.TFrame", background=self.card_bg, relief="groove")
        style.configure("TProgressbar", thickness=18)
        style.configure("Primary.TButton", font=self.font_bold, background=self.primary_color, foreground="#ffffff")

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ── 1. TIÊU ĐỀ ────────────────────────────────────────────────────────
        header_frame = tk.Frame(main_frame, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_lbl = tk.Label(
            header_frame,
            text="📚 MANGA & PIXIV DOWNLOADER",
            font=("Segoe UI", 16, "bold"),
            bg=self.bg_color,
            fg="#1e40af",
        )
        title_lbl.pack(side=tk.LEFT)

        sub_lbl = tk.Label(
            header_frame,
            text="Hỗ trợ tải truyện tranh & full ảnh tác phẩm Pixiv độ phân giải gốc",
            font=("Segoe UI", 9, "italic"),
            bg=self.bg_color,
            fg="#6b7280",
        )
        sub_lbl.pack(side=tk.LEFT, padx=15, pady=(5, 0))

        # ── 2. KHUNG NHẬP LINK (TRUYỆN HOẶC PIXIV) ─────────────────────────────
        url_frame = tk.LabelFrame(main_frame, text=" 🔗 Nhập link truyện hoặc link Pixiv ", font=self.font_bold, bg=self.bg_color, padx=12, pady=10)
        url_frame.pack(fill=tk.X, pady=(0, 10))

        self.url_var = tk.StringVar(value="https://www.pixiv.net/en/artworks/47385304")
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, font=("Segoe UI", 10))
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        btn_paste = tk.Button(
            url_frame,
            text="📋 Dán",
            font=self.font_main,
            bg="#e5e7eb",
            relief="groove",
            command=self._paste_clipboard,
            cursor="hand2",
            padx=10,
        )
        btn_paste.pack(side=tk.LEFT, padx=(0, 6))

        btn_cookie = tk.Button(
            url_frame,
            text="🍪 Cookie Pixiv",
            font=self.font_main,
            bg="#e5e7eb",
            relief="groove",
            command=self._open_cookie_dialog,
            cursor="hand2",
            padx=10,
        )
        btn_cookie.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_fetch = tk.Button(
            url_frame,
            text="🔍 Lấy thông tin",
            font=self.font_bold,
            bg=self.primary_color,
            fg="#ffffff",
            relief="flat",
            command=self._start_fetch_info,
            cursor="hand2",
            padx=14,
            pady=4,
        )
        self.btn_fetch.pack(side=tk.LEFT)

        # ── 3. KHUNG THÔNG TIN TRUYỆN / BÀI VIẾT (CARD) ───────────────────────
        self.info_card = tk.LabelFrame(main_frame, text=" 📖 Thông tin chi tiết ", font=self.font_bold, bg=self.card_bg, padx=12, pady=10)
        self.info_card.pack(fill=tk.X, pady=(0, 10))

        # Ảnh bìa / Thumbnail (bên trái)
        self.cover_lbl = tk.Label(self.info_card, text="[Ảnh xem trước]", bg="#e5e7eb", width=14, height=7)
        self.cover_lbl.pack(side=tk.LEFT, padx=(0, 15))

        # Chi tiết chữ (bên phải)
        detail_frame = tk.Frame(self.info_card, bg=self.card_bg)
        detail_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.lbl_manga_title = tk.Label(
            detail_frame, text="Chưa lấy thông tin", font=self.font_title, bg=self.card_bg, fg="#111827", anchor="w"
        )
        self.lbl_manga_title.pack(fill=tk.X)

        self.lbl_manga_author = tk.Label(
            detail_frame, text="Tác giả / Artist: --", font=self.font_main, bg=self.card_bg, fg="#4b5563", anchor="w"
        )
        self.lbl_manga_author.pack(fill=tk.X, pady=2)

        self.lbl_manga_status = tk.Label(
            detail_frame, text="Trạng thái: --", font=self.font_main, bg=self.card_bg, fg="#4b5563", anchor="w"
        )
        self.lbl_manga_status.pack(fill=tk.X, pady=2)

        self.lbl_manga_chaps = tk.Label(
            detail_frame, text="Tổng số: 0", font=self.font_bold, bg=self.card_bg, fg="#059669", anchor="w"
        )
        self.lbl_manga_chaps.pack(fill=tk.X, pady=2)

        # ── 4. CẤU HÌNH TẢI VỀ ───────────────────────────────────────────────
        opt_frame = tk.LabelFrame(main_frame, text=" ⚙️ Tùy chọn tải về ", font=self.font_bold, bg=self.bg_color, padx=12, pady=10)
        opt_frame.pack(fill=tk.X, pady=(0, 10))

        # Thư mục lưu
        dir_frame = tk.Frame(opt_frame, bg=self.bg_color)
        dir_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(dir_frame, text="Thư mục lưu:", font=self.font_bold, bg=self.bg_color).pack(side=tk.LEFT)
        self.out_dir_var = tk.StringVar(value=os.path.abspath("downloads"))
        entry_dir = ttk.Entry(dir_frame, textvariable=self.out_dir_var, font=("Segoe UI", 9))
        entry_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        btn_browse = tk.Button(
            dir_frame,
            text="📁 Chọn...",
            font=self.font_main,
            bg="#e5e7eb",
            relief="groove",
            command=self._browse_dir,
            cursor="hand2",
        )
        btn_browse.pack(side=tk.LEFT)

        # Lựa chọn phạm vi tải
        chap_mode_frame = tk.Frame(opt_frame, bg=self.bg_color)
        chap_mode_frame.pack(fill=tk.X, pady=(0, 8))

        self.lbl_range_title = tk.Label(chap_mode_frame, text="Phạm vi tải:", font=self.font_bold, bg=self.bg_color)
        self.lbl_range_title.pack(side=tk.LEFT, padx=(0, 10))

        self.mode_var = tk.StringVar(value="all")

        self.rb_all = tk.Radiobutton(
            chap_mode_frame,
            text="Toàn bộ",
            variable=self.mode_var,
            value="all",
            bg=self.bg_color,
            font=self.font_main,
            command=self._update_mode_state,
        )
        self.rb_all.pack(side=tk.LEFT, padx=5)

        self.rb_range = tk.Radiobutton(
            chap_mode_frame,
            text="Theo khoảng (từ - đến):",
            variable=self.mode_var,
            value="range",
            bg=self.bg_color,
            font=self.font_main,
            command=self._update_mode_state,
        )
        self.rb_range.pack(side=tk.LEFT, padx=5)

        self.from_var = tk.StringVar(value="1")
        self.entry_from = ttk.Entry(chap_mode_frame, textvariable=self.from_var, width=5, state="disabled")
        self.entry_from.pack(side=tk.LEFT, padx=2)

        self.lbl_to = tk.Label(chap_mode_frame, text="đến", bg=self.bg_color)
        self.lbl_to.pack(side=tk.LEFT, padx=2)

        self.to_var = tk.StringVar(value="10")
        self.entry_to = ttk.Entry(chap_mode_frame, textvariable=self.to_var, width=5, state="disabled")
        self.entry_to.pack(side=tk.LEFT, padx=2)

        self.rb_custom = tk.Radiobutton(
            chap_mode_frame,
            text="Tự nhập:",
            variable=self.mode_var,
            value="custom",
            bg=self.bg_color,
            font=self.font_main,
            command=self._update_mode_state,
        )
        self.rb_custom.pack(side=tk.LEFT, padx=(15, 2))

        self.custom_var = tk.StringVar(value="1, 3, 5-8")
        self.entry_custom = ttk.Entry(chap_mode_frame, textvariable=self.custom_var, width=14, state="disabled")
        self.entry_custom.pack(side=tk.LEFT, padx=2)

        # Số luồng & Bỏ qua file cũ
        threads_frame = tk.Frame(opt_frame, bg=self.bg_color)
        threads_frame.pack(fill=tk.X)

        tk.Label(threads_frame, text="Số luồng tải ảnh song song:", font=self.font_main, bg=self.bg_color).pack(side=tk.LEFT)
        self.threads_var = tk.IntVar(value=6)
        sp_threads = ttk.Spinbox(threads_frame, from_=1, to=16, textvariable=self.threads_var, width=4)
        sp_threads.pack(side=tk.LEFT, padx=(6, 25))

        self.skip_var = tk.BooleanVar(value=True)
        self.cb_skip = tk.Checkbutton(
            threads_frame,
            text="Bỏ qua file đã có sẵn (Tiết kiệm thời gian)",
            variable=self.skip_var,
            bg=self.bg_color,
            font=self.font_main,
        )
        self.cb_skip.pack(side=tk.LEFT)

        # ── 5. THANH TIẾN TRÌNH & NÚT HÀNH ĐỘNG ──────────────────────────────
        act_frame = tk.Frame(main_frame, bg=self.bg_color)
        act_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_download = tk.Button(
            act_frame,
            text="🚀 BẮT ĐẦU TẢI",
            font=("Segoe UI", 11, "bold"),
            bg="#16a34a",
            fg="#ffffff",
            relief="flat",
            command=self._start_download,
            cursor="hand2",
            padx=20,
            pady=7,
        )
        self.btn_download.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_stop = tk.Button(
            act_frame,
            text="⏹️ Dừng",
            font=self.font_bold,
            bg="#dc2626",
            fg="#ffffff",
            relief="flat",
            command=self._stop_download,
            cursor="hand2",
            state="disabled",
            padx=16,
            pady=7,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 10))

        btn_open_folder = tk.Button(
            act_frame,
            text="📂 Mở thư mục tải",
            font=self.font_bold,
            bg="#4b5563",
            fg="#ffffff",
            relief="flat",
            command=self._open_output_dir,
            cursor="hand2",
            padx=14,
            pady=7,
        )
        btn_open_folder.pack(side=tk.RIGHT)

        # Thanh tiến trình
        prog_frame = tk.Frame(main_frame, bg=self.bg_color)
        prog_frame.pack(fill=tk.X, pady=(0, 8))

        self.lbl_status = tk.Label(
            prog_frame,
            text="Sẵn sàng.",
            font=self.font_main,
            bg=self.bg_color,
            fg="#1f2937",
            anchor="w",
        )
        self.lbl_status.pack(fill=tk.X, pady=(0, 4))

        self.prog_bar = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate")
        self.prog_bar.pack(fill=tk.X)

        # ── 6. KHUNG NHẬT KÝ (LOG) ───────────────────────────────────────────
        log_frame = tk.LabelFrame(main_frame, text=" 📝 Nhật ký tải (Log) ", font=self.font_bold, bg=self.bg_color, padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_log = ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#ffffff",
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    # ── CÁC HÀM XỬ LÝ SỰ KIỆN ──────────────────────────────────────────────
    def _paste_clipboard(self):
        try:
            content = self.root.clipboard_get().strip()
            if content:
                self.url_var.set(content)
        except Exception:
            pass

    def _browse_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.out_dir_var.get())
        if chosen:
            self.out_dir_var.set(chosen)

    def _open_cookie_dialog(self):
        """Mở cửa sổ cài đặt Pixiv Cookie (PHPSESSID)."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Cài đặt Pixiv Cookie (Tùy chọn)")
        dlg.geometry("540x310")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        frame = tk.Frame(dlg, padx=15, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text="🍪 Cài đặt Cookie Pixiv (PHPSESSID)",
            font=("Segoe UI", 12, "bold"),
            fg="#1e40af",
        ).pack(anchor="w", pady=(0, 8))

        desc = (
            "• Đối với các tác phẩm công khai thông thường: Bạn KHÔNG CẦN nhập cookie.\n"
            "• Đối với các tác phẩm giới hạn (R-18 hoặc yêu cầu đăng nhập Pixiv):\n"
            "   1. Đăng nhập Pixiv trên trình duyệt web của bạn.\n"
            "   2. Bấm F12 -> tab Application (hoặc Storage) -> Cookies -> https://www.pixiv.net\n"
            "   3. Copy giá trị chuỗi PHPSESSID và dán vào ô bên dưới."
        )
        tk.Label(frame, text=desc, justify=tk.LEFT, font=("Segoe UI", 9), fg="#4b5563").pack(anchor="w", pady=(0, 10))

        tk.Label(frame, text="PHPSESSID:", font=self.font_bold).pack(anchor="w")
        cookie_var = tk.StringVar(value=get_pixiv_cookie())
        entry = ttk.Entry(frame, textvariable=cookie_var, font=("Consolas", 10), width=50)
        entry.pack(fill=tk.X, pady=(2, 15))

        btn_box = tk.Frame(frame)
        btn_box.pack(fill=tk.X)

        def save_and_close():
            val = cookie_var.get().strip()
            set_pixiv_cookie(val)
            messagebox.showinfo("Đã lưu", "Đã lưu cài đặt Cookie Pixiv thành công!", parent=dlg)
            dlg.destroy()

        def clear_cookie():
            cookie_var.set("")
            set_pixiv_cookie("")
            messagebox.showinfo("Đã xóa", "Đã xóa Cookie Pixiv.", parent=dlg)

        btn_save = tk.Button(btn_box, text="💾 Lưu cấu hình", font=self.font_bold, bg="#16a34a", fg="#ffffff", padx=12, pady=4, relief="flat", command=save_and_close)
        btn_save.pack(side=tk.LEFT, padx=(0, 10))

        btn_clear = tk.Button(btn_box, text="🗑️ Xóa Cookie", font=self.font_main, bg="#e5e7eb", padx=10, pady=4, relief="groove", command=clear_cookie)
        btn_clear.pack(side=tk.LEFT, padx=(0, 10))

        btn_cancel = tk.Button(btn_box, text="Đóng", font=self.font_main, bg="#e5e7eb", padx=10, pady=4, relief="groove", command=dlg.destroy)
        btn_cancel.pack(side=tk.RIGHT)

    def _update_mode_state(self):
        mode = self.mode_var.get()
        self.entry_from.config(state="normal" if mode == "range" else "disabled")
        self.entry_to.config(state="normal" if mode == "range" else "disabled")
        self.entry_custom.config(state="normal" if mode == "custom" else "disabled")

    def _log(self, text: str):
        self.log_queue.put(("log", text))

    def _check_queue(self):
        """Đọc và cập nhật giao diện an toàn từ hàng đợi đa luồng."""
        try:
            while True:
                msg_type, data = self.log_queue.get_nowait()
                if msg_type == "log":
                    self.txt_log.insert(tk.END, data + "\n")
                    self.txt_log.see(tk.END)
                elif msg_type == "status":
                    self.lbl_status.config(text=data)
                elif msg_type == "progress":
                    val, max_val = data
                    self.prog_bar["value"] = val
                    self.prog_bar["maximum"] = max_val
                elif msg_type == "fetch_done":
                    self._on_fetch_success(data)
                elif msg_type == "fetch_error":
                    self.btn_fetch.config(state="normal")
                    self.lbl_status.config(text=f"Lỗi: {data}")
                    messagebox.showerror("Lỗi", f"Không thể lấy thông tin:\n{data}")
                elif msg_type == "download_done":
                    self._on_download_finished(data)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._check_queue)

    def _start_fetch_info(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập link truyện hoặc link Pixiv!")
            return

        self.btn_fetch.config(state="disabled")
        self.lbl_status.config(text="Đang kết nối và lấy thông tin...")
        self._log(f"🔍 Đang kiểm tra link: {url}")

        threading.Thread(target=self._worker_fetch_info, args=(url,), daemon=True).start()

    def _worker_fetch_info(self, url: str):
        scraper = MangaScraper()
        try:
            info = scraper.fetch_manga_info(url)
            self.log_queue.put(("fetch_done", info))
        except Exception as e:
            self.log_queue.put(("fetch_error", str(e)))
        finally:
            scraper.close()

    def _on_fetch_success(self, info: MangaInfo):
        self.manga_info = info
        self.btn_fetch.config(state="normal")

        self.lbl_manga_title.config(text=info.title)
        self.lbl_manga_author.config(text=f"Tác giả / Artist: {info.author}")
        self.lbl_manga_status.config(text=f"Trạng thái: {info.status}")

        if info.is_single_post:
            # Giao diện cho tác phẩm Pixiv
            self.lbl_status.config(text=f"Đã lấy thông tin Pixiv: {info.title} ({info.total_chapters} ảnh)")
            self.lbl_manga_chaps.config(text=f"Tổng số ảnh: {info.total_chapters} ảnh", fg="#2563eb")
            self.lbl_range_title.config(text="Phạm vi ảnh:")
            self.rb_all.config(text=f"Toàn bộ ảnh trong bài ({info.total_chapters} ảnh)")
            self.rb_range.config(text="Theo khoảng (từ ảnh - đến):")
            self.rb_custom.config(text="Tự chọn ảnh:")
            self.cb_skip.config(text="Bỏ qua các ảnh đã có sẵn")
            self.btn_download.config(text="🚀 BẮT ĐẦU TẢI ẢNH PIXIV")

            if info.chapters:
                self.from_var.set("1")
                self.to_var.set(str(info.total_chapters))
                self.custom_var.set(f"1-{info.total_chapters}")

            self._log(f"📖 Tác phẩm Pixiv: {info.title}")
            self._log(f"🎨 Artist: {info.author}")
            self._log(f"🖼️ Tổng cộng: {info.total_chapters} ảnh (độ phân giải gốc)")
        else:
            # Giao diện cho truyện tranh nhiều chap
            self.lbl_status.config(text=f"Đã lấy thông tin: {info.title} ({info.total_chapters} chương)")
            self.lbl_manga_chaps.config(text=f"Tổng số chương: {info.total_chapters}", fg="#059669")
            self.lbl_range_title.config(text="Phạm vi tải:")
            self.rb_all.config(text="Toàn bộ chương")
            self.rb_range.config(text="Theo khoảng (từ - đến):")
            self.rb_custom.config(text="Tự nhập:")
            self.cb_skip.config(text="Bỏ qua chương đã tải đủ ảnh (Tiết kiệm thời gian)")
            self.btn_download.config(text="🚀 BẮT ĐẦU TẢI TRUYỆN")

            if info.chapters:
                self.from_var.set(str(int(info.chapters[0].chapter_num)))
                self.to_var.set(str(int(info.chapters[-1].chapter_num)))
                self.custom_var.set(f"1-{int(info.chapters[-1].chapter_num)}")

            self._log(f"📖 Tên truyện: {info.title}")
            self._log(f"📚 Tìm thấy {info.total_chapters} chương hợp lệ.")

        # Tải thumbnail bìa / xem trước
        if info.cover_url:
            threading.Thread(target=self._load_cover_thumbnail, args=(info.cover_url,), daemon=True).start()

    def _load_cover_thumbnail(self, cover_url: str):
        try:
            # Sử dụng Referer Pixiv nếu ảnh nằm trên máy chủ i.pximg.net
            referer = "https://www.pixiv.net/" if ("pximg.net" in cover_url) else "https://truyenqq.com.co/"
            resp = httpx.get(
                cover_url,
                headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
                timeout=12,
            )
            if resp.status_code == 200:
                img_data = Image.open(io.BytesIO(resp.content))
                img_data.thumbnail((120, 150))
                self.cover_img_tk = ImageTk.PhotoImage(img_data)
                self.cover_lbl.config(image=self.cover_img_tk, text="")
        except Exception:
            pass

    def _get_selected_chapters(self) -> List[ChapterInfo]:
        if not self.manga_info or not self.manga_info.chapters:
            return []

        mode = self.mode_var.get()
        chapters = self.manga_info.chapters

        if mode == "all":
            return chapters

        elif mode == "range":
            try:
                start = float(self.from_var.get().strip())
                end = float(self.to_var.get().strip())
                if start > end:
                    start, end = end, start
                return [c for c in chapters if start <= c.chapter_num <= end]
            except ValueError:
                label_term = "ảnh" if self.manga_info.is_single_post else "chương"
                messagebox.showerror("Lỗi", f"Khoảng {label_term} nhập vào không hợp lệ!")
                return []

        elif mode == "custom":
            from cli import parse_custom_selection
            raw = self.custom_var.get().strip()
            if not raw:
                label_term = "ảnh" if self.manga_info.is_single_post else "chương"
                messagebox.showerror("Lỗi", f"Vui lòng nhập danh sách {label_term}!")
                return []
            return parse_custom_selection(raw, chapters)

        return chapters

    def _start_download(self):
        if not self.manga_info:
            messagebox.showwarning("Cảnh báo", "Vui lòng bấm 'Lấy thông tin' trước khi tải!")
            return

        selected = self._get_selected_chapters()
        if not selected:
            label_term = "ảnh" if self.manga_info.is_single_post else "chương"
            messagebox.showwarning("Cảnh báo", f"Không có {label_term} nào được chọn để tải!")
            return

        self.btn_download.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_fetch.config(state="disabled")

        out_dir = self.out_dir_var.get().strip() or "downloads"
        workers = max(1, min(16, self.threads_var.get()))
        skip = self.skip_var.get()

        self.downloader = MangaDownloader(
            output_dir=out_dir,
            max_workers=workers,
            skip_existing=skip,
        )

        unit = "ẢNH" if self.manga_info.is_single_post else "CHƯƠNG"
        self._log(f"🚀 BẮT ĐẦU TẢI {len(selected)} {unit}...")
        self._log(f"📁 Lưu tại: {os.path.abspath(out_dir)}\\{self.manga_info.title}\\")

        self.download_thread = threading.Thread(
            target=self._worker_download,
            args=(self.manga_info, selected),
            daemon=True,
        )
        self.download_thread.start()

    def _worker_download(self, manga: MangaInfo, selected_chaps: List[ChapterInfo]):
        scraper = MangaScraper()

        if manga.is_single_post:
            def on_prog(chap_idx: int, total_chaps: int, img_idx: int, total_imgs: int, fname: str):
                pct = (img_idx / max(1, total_imgs)) * 100
                self.log_queue.put(("progress", (int(pct), 100)))
                text = f"Đang tải ảnh Pixiv {img_idx}/{total_imgs} ({fname}) - {pct:.1f}%"
                self.log_queue.put(("status", text))
        else:
            def on_prog(chap_idx: int, total_chaps: int, img_idx: int, total_imgs: int, fname: str):
                overall_pct = ((chap_idx - 1) / total_chaps) + ((img_idx / max(1, total_imgs)) / total_chaps)
                self.log_queue.put(("progress", (int(overall_pct * 100), 100)))
                text = f"Đang tải {chap_idx}/{total_chaps} ({selected_chaps[chap_idx-1].display_name}): Ảnh {img_idx}/{total_imgs} ({fname})"
                self.log_queue.put(("status", text))

        try:
            self.downloader.download_manga(
                manga=manga,
                chapters_to_download=selected_chaps,
                fetch_images_func=scraper.fetch_chapter_images,
                on_progress=on_prog,
                on_log=self._log,
            )
            self.log_queue.put(("download_done", True))
        except Exception as e:
            self._log(f"❌ Có lỗi trong quá trình tải: {e}")
            self.log_queue.put(("download_done", False))
        finally:
            scraper.close()

    def _stop_download(self):
        if self.downloader:
            self.downloader.cancel()
            self._log("⏹️ Đang gửi tín hiệu dừng tiến trình...")
            self.btn_stop.config(state="disabled")

    def _on_download_finished(self, success: bool):
        self.btn_download.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_fetch.config(state="normal")
        self.prog_bar["value"] = 100

        if success:
            if self.manga_info and self.manga_info.is_single_post:
                self.lbl_status.config(text="🎉 Hoàn thành tải toàn bộ ảnh Pixiv đã chọn!")
                manga_dir = os.path.join(self.out_dir_var.get(), sanitize_filename(self.manga_info.title))
                msg = f"Đã tải thành công các ảnh Pixiv!\nLưu tại:\n{os.path.abspath(manga_dir)}\n\nBạn có muốn mở thư mục ngay bây giờ?"
            else:
                self.lbl_status.config(text="🎉 Hoàn thành tải toàn bộ chương được chọn!")
                manga_dir = os.path.join(self.out_dir_var.get(), sanitize_filename(self.manga_info.title))
                msg = f"Đã tải thành công các chương truyện!\nLưu tại:\n{os.path.abspath(manga_dir)}\n\nBạn có muốn mở thư mục ngay bây giờ?"

            if messagebox.askyesno("Thành công", msg):
                self._open_output_dir()
        else:
            self.lbl_status.config(text="Đã dừng hoặc có lỗi xảy ra.")

    def _open_output_dir(self):
        target = self.out_dir_var.get().strip() or "downloads"
        if self.manga_info:
            specific = os.path.join(target, sanitize_filename(self.manga_info.title))
            if os.path.exists(specific):
                target = specific

        os.makedirs(target, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(os.path.abspath(target))


def run_gui():
    root = tk.Tk()
    app = MangaDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
