# Tool Leech Manga & Pixiv Downloader - Tải Truyện Tranh & Ảnh Pixiv Đa Luồng

Phần mềm hỗ trợ:
1. **Truyện tranh (Manga)**: Tự động tải (leech) toàn bộ các chương từ link web (chuyên biệt cho TruyenQQ và các trang tương tự) thành **từng thư mục ảnh riêng biệt** cho mỗi chương.
2. **Pixiv (Tác phẩm / Bộ ảnh)**: Tự động phân tích và tải **toàn bộ ảnh trong bài viết Pixiv** (ví dụ: `https://www.pixiv.net/en/artworks/47385304`) với **độ phân giải gốc cao nhất (Original Quality)**, lưu trực tiếp vào thư mục tác phẩm.

---

## 🌟 Tính Năng Nổi Bật

1. **Hỗ Trợ Tải Full Ảnh Pixiv**:
   - Nhập bất kỳ link tác phẩm Pixiv nào (`https://www.pixiv.net/en/artworks/47385304`, link rút gọn hoặc chỉ cần mã ID).
   - Tự động lấy tiêu đề, tác giả (artist), tổng số ảnh và ảnh xem trước.
   - Cho phép tải toàn bộ ảnh trong bài, hoặc tải theo khoảng (ví dụ: từ ảnh 1 đến 10), hoặc chọn các ảnh cụ thể.
   - Tự động vượt cơ chế chặn Referer của máy chủ ảnh `i.pximg.net`.
   - Lưu ảnh gốc với độ phân giải cao nhất (`.png` / `.jpg`). Nếu ảnh gốc gặp sự cố, tự động fallback về chất lượng cao `regular`.
   - Hỗ trợ cấu hình **Pixiv Cookie (`PHPSESSID`)** để tải các tác phẩm giới hạn độ tuổi (R-18) hoặc yêu cầu đăng nhập.

2. **Cấu Trúc Thư Mục Chuẩn Đẹp**:
   - **Đối với truyện tranh**:
     ```text
     downloads/
       └── Tên Truyện/
             ├── Chương 001/
             │     ├── 001.jpg
             │     └── ...
             └── Chương 002/
     ```
   - **Đối với Pixiv**:
     ```text
     downloads/
       └── [Pixiv] 47385304 - Tên Tác Phẩm/
             ├── 001.png
             ├── 002.png
             ├── 003.png
             └── ...
     ```
   - Ảnh được đánh số thứ tự chuẩn 3-4 chữ số (`001.png`, `002.png`...) giúp xem trên máy tính, điện thoại hoặc các app đọc ảnh/truyện tranh luôn đúng thứ tự 100%.

3. **Giao Diện Đồ Họa (GUI) & Dòng Lệnh (CLI)**:
   - **Giao diện trực quan**: Dán link -> Bấm "Lấy thông tin" -> Chọn "Toàn bộ ảnh" / "Khoảng ảnh" -> Bấm "Bắt đầu tải".
   - **Nút "Cookie Pixiv"**: Dễ dàng lưu cookie `PHPSESSID` từ trình duyệt khi cần tải nội dung R-18.
   - **Dòng lệnh (CLI)**: Tự động nhận diện link truyện hay link Pixiv để đưa ra menu lựa chọn tương ứng.

4. **Tốc Độ Cao & Ổn Định (Đa Luồng)**:
   - Tải song song đa luồng (1 đến 16 luồng, mặc định 6 luồng).
   - Bỏ qua các ảnh đã tải xong trước đó (tránh tải trùng).
   - Cơ chế tự động thử lại (Retry) khi gặp sự cố mạng hoặc server bận.

---

## 🚀 Hướng Dẫn Sử Dụng

### Cách 1: Sử dụng Giao Diện Đồ Họa (GUI)
- Nhấp đúp chuột vào file: **`Chay_Giao_Dien_GUI.bat`** *(hoặc chạy: `python main.py`)*
- Dán link truyện hoặc link bài Pixiv vào ô:
  - Link Pixiv ví dụ: `https://www.pixiv.net/en/artworks/47385304`
  - Link truyện ví dụ: `https://truyenqq.com.co/truyen/shishunki-renaissance-david-kun`
- Bấm **"🔍 Lấy thông tin"**.
- Tùy chọn phạm vi tải:
  - **Toàn bộ ảnh**: Tải hết toàn bộ ảnh trong bài Pixiv đó (Mặc định).
  - **Theo khoảng**: Ví dụ từ ảnh 1 đến 10.
  - **Tự chọn**: Ví dụ `1, 3, 5-8`.
- Bấm **"🚀 BẮT ĐẦU TẢI"**.
- Sau khi tải xong, bấm **"📂 Mở thư mục tải"** để xem ngay.

> [!TIP]
> **Tải bài viết Pixiv R-18 hoặc yêu cầu đăng nhập:**
> Bấm nút **"🍪 Cookie Pixiv"** trên giao diện, đăng nhập tài khoản Pixiv trên trình duyệt web, ấn F12 -> tab Application -> Cookies -> `pixiv.net`, copy chuỗi `PHPSESSID` dán vào và bấm Lưu. Với bài viết công khai, bạn không cần cài đặt cookie này.

---

### Cách 2: Sử dụng Dòng Lệnh (CLI)
- Nhấp đúp chuột vào file: **`Chay_Dong_Lenh_CLI.bat`** *(hoặc mở PowerShell/CMD chạy: `python cli.py`)*
- Nhập link truyện hoặc Pixiv theo hướng dẫn.

**Các lệnh tắt với tham số:**
```bash
# Tải toàn bộ ảnh trong bài Pixiv
python cli.py "https://www.pixiv.net/en/artworks/47385304" --all

# Tải từ ảnh 1 đến ảnh 10 bài Pixiv với 8 luồng
python cli.py "https://www.pixiv.net/en/artworks/47385304" --range 1-10 --threads 8

# Tải bài Pixiv R-18 kèm cookie
python cli.py "https://www.pixiv.net/en/artworks/XXXXXXXX" --all --cookie "YOUR_PHPSESSID"

# Tải toàn bộ truyện tranh TruyenQQ
python cli.py "https://truyenqq.com.co/truyen/shishunki-renaissance-david-kun" --all
```

---

## 📦 Cài Đặt Thư Viện (Nếu Chạy Trên Máy Mới)

Nếu bạn copy thư mục này sang máy tính khác chưa có thư viện Python:
```bash
pip install -r requirements.txt
```
*(Gồm 3 thư viện cơ bản: `httpx`, `beautifulsoup4`, `pillow`)*
