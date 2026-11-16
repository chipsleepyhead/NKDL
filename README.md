# NYC Taxi Intelligence — triển khai online

Ứng dụng Streamlit gốc, dữ liệu DuckDB gốc và các kết quả ML gốc. Không huấn luyện lại mô hình. Các file `.joblib` (mô hình đã huấn luyện) được loại khỏi gói triển khai vì app chỉ **đọc kết quả ML đã xuất** và không tải `.joblib`. Kết quả CSV/JSON được giữ nguyên.

## Triển khai cho thầy xem bằng URL

1. Giải nén ZIP và tạo GitHub repository **Public**. Upload toàn bộ nội dung thư mục này lên nhánh `main`, giữ nguyên cấu trúc thư mục `data/`, `my_results/`, `.streamlit/`.
2. Lưu ý file `data/nyc_taxi_demo.duckdb` gần 100 MB, nằm sát giới hạn GitHub 100 MB/file. Nếu GitHub từ chối, cần Git LFS hoặc lưu database ở nguồn khác và điều chỉnh cơ chế tải dữ liệu.
3. Mở https://share.streamlit.io/ và đăng nhập GitHub, chọn **Create app → Deploy a public app from GitHub**.
4. Chọn repository, branch `main`, entrypoint `app.py`, sau đó Deploy.
5. Chia sẻ URL `https://<ten-app>.streamlit.app/` với thầy. Thầy chỉ cần trình duyệt, không phải tải/cài gì.

**GitHub Pages (`username.github.io`) không chạy trực tiếp Python, DuckDB server-side hay Streamlit.** Bản này dùng GitHub lưu mã nguồn + Streamlit Community Cloud chạy web để giữ nguyên tính năng.

## Cấu trúc
- `app.py`: ứng dụng gốc, 7 trang và bộ lọc
- `data/nyc_taxi_demo.duckdb`: 5 Data Marts gốc
- `data/taxi_zones.geojson`: bản đồ ranh giới gốc
- `my_results/`: CSV/JSON và biểu đồ kết quả ML gốc
- `requirements.txt`: thư viện cần thiết

**Lưu ý:** `my_results` có thể chứa thông tin phân tích; cân nhắc quyền công khai dữ liệu trước khi đưa lên repo Public.
