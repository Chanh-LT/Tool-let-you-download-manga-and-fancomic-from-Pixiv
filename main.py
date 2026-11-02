"""
Điểm khởi chạy chính (Main Entry Point) cho Tool Leech Manga.
- Chạy trực tiếp không tham số: Tự động mở giao diện đồ họa (GUI).
- Chạy kèm tham số hoặc cờ --cli: Khởi động giao diện dòng lệnh (CLI).
"""

import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] not in ("--gui", "-g"):
        # Có tham số truyền vào -> Chạy CLI
        if sys.argv[1] == "--cli":
            sys.argv.pop(1)
        from cli import main as cli_main
        cli_main()
    else:
        # Không có tham số hoặc cờ --gui -> Mở GUI Tkinter
        try:
            from gui import run_gui
            run_gui()
        except Exception as e:
            print(f"Không thể khởi động giao diện đồ họa (GUI): {e}")
            print("Đang chuyển sang chế độ dòng lệnh (CLI)...")
            from cli import main as cli_main
            cli_main()
