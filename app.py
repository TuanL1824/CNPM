from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'khoa_bao_mat_he_thong_dich_vu'

# ==========================================
# 1. DATABASE SCHEMA (Dựa trên Class Diagram)
# ==========================================
def init_db():
    conn = sqlite3.connect('hethong.db')
    c = conn.cursor()
    
    # THÊM CỘT 'role' (Mặc định là 'khachhang')
    c.execute('''CREATE TABLE IF NOT EXISTS taikhoan 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE NOT NULL, 
                  password_hash TEXT NOT NULL,
                  email TEXT UNIQUE,
                  hoTen TEXT,
                  soDienThoai TEXT,
                  role TEXT DEFAULT 'khachhang')''')
                  
    # Tạo bảng goidichvu và donhang (Giữ nguyên như cũ của bạn)
    c.execute('''CREATE TABLE IF NOT EXISTS goidichvu (id INTEGER PRIMARY KEY AUTOINCREMENT, maGoi TEXT UNIQUE NOT NULL, tenGoi TEXT NOT NULL, giaCuoc REAL NOT NULL, moTa TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS donhang (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, goidichvu_id INTEGER, ngayTao DATETIME DEFAULT CURRENT_TIMESTAMP, trangThai TEXT DEFAULT 'Chờ thanh toán', tongTien REAL, FOREIGN KEY(user_id) REFERENCES taikhoan(id), FOREIGN KEY(goidichvu_id) REFERENCES goidichvu(id))''')

    # TỰ ĐỘNG TẠO TÀI KHOẢN NHÂN VIÊN MẶC ĐỊNH
    admin_exist = c.execute("SELECT * FROM taikhoan WHERE role = 'nhanvien'").fetchone()
    if not admin_exist:
        hashed_pw = generate_password_hash("123456") # Mật khẩu mặc định là 123456
        c.execute("INSERT INTO taikhoan (username, password_hash, hoTen, role) VALUES (?, ?, ?, ?)", 
                  ('admin', hashed_pw, 'Quản Trị Viên', 'nhanvien'))

    # Thêm dữ liệu gói dịch vụ mẫu... (Giữ nguyên)
    if c.execute('SELECT COUNT(*) FROM goidichvu').fetchone()[0] == 0:
        c.executemany('INSERT INTO goidichvu (maGoi, tenGoi, giaCuoc, moTa) VALUES (?, ?, ?, ?)', [('GOI_CB', 'Gói Cơ Bản', 50000, 'Nhận được 90GB/tháng. Cộng 3GB mỗi ngày'), ('GOI_PRO', 'Gói Chuyên Nghiệp', 150000, 'Truy cập mạng xã hội (facebook, youtube...) tẹt ga trong một tháng. Cộng 3GB mỗi ngày'), ('GOI_VIP', 'Gói VIP', 300000, 'Không giới hạn truy cập mạng trong một tháng, thích làm gì thì làm.')])
        
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect('hethong.db')
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================
# 2. XỬ LÝ LOGIC (Dựa trên Activity/Sequence Diagram)
# ==========================================

# Luồng Xem danh sách gói (Sequence Trang 12)
@app.route('/')
# Luồng Xem danh sách và Tìm kiếm gói (Trang 7, 12)
@app.route('/')
def index():
    # Lấy từ khóa tìm kiếm từ URL (nếu có)
    tu_khoa = request.args.get('q', '') 
    
    conn = get_db()
    if tu_khoa:
        # Nếu có từ khóa, dùng lệnh LIKE để tìm gần đúng theo Tên hoặc Mã gói
        chuoi_tim_kiem = f'%{tu_khoa}%'
        goi_dich_vu = conn.execute(
            'SELECT * FROM goidichvu WHERE tenGoi LIKE ? OR maGoi LIKE ?', 
            (chuoi_tim_kiem, chuoi_tim_kiem)
        ).fetchall()
    else:
        # Nếu không có từ khóa, lấy toàn bộ danh sách
        goi_dich_vu = conn.execute('SELECT * FROM goidichvu').fetchall()
        
    conn.close()
    
    # Truyền thêm biến tu_khoa ra giao diện để giữ lại chữ người dùng vừa gõ
    return render_template('index.html', goi_dich_vu=goi_dich_vu, tu_khoa=tu_khoa)
# ==========================================
# LUỒNG ĐĂNG NHẬP
# ==========================================
# ==========================================
# LUỒNG ĐĂNG NHẬP
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # 1. Lấy dữ liệu người dùng vừa nhập trên giao diện
        username = request.form['username']
        password = request.form['password']

        # 2. Kết nối Database và tìm tài khoản có username đó
        conn = get_db()
        user = conn.execute('SELECT * FROM taikhoan WHERE username = ?', (username,)).fetchone()
        conn.close()

        # 3. So sánh mật khẩu và thiết lập Phiên đăng nhập (Session)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['ho_ten'] = user['hoTen']
            session['role'] = user['role'] # LƯU ROLE VÀO SESSION

            # 4. ĐIỀU HƯỚNG DỰA TRÊN ROLE
            if user['role'] == 'nhanvien':
                return redirect(url_for('admin_users')) # Chuyển đến trang nhân viên
            else:
                return redirect(url_for('index')) # Chuyển đến trang khách hàng
        else:
            flash('Sai tài khoản hoặc mật khẩu!', 'danger')

    return render_template('login.html')
# ==========================================
# LUỒNG QUÊN MẬT KHẨU (Gửi OTP)
# ==========================================
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        
        conn = get_db()
        user = conn.execute('SELECT * FROM taikhoan WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user:
            # 1. Tạo mã OTP ngẫu nhiên 6 chữ số
            otp = str(random.randint(100000, 999999))
            
            # 2. Lưu tạm email và OTP vào phiên làm việc (Session) để lát nữa kiểm tra
            session['reset_email'] = email
            session['reset_otp'] = otp

            # 3. MÔ PHỎNG GỬI EMAIL: Thay vì gửi email thật, ta hiện mã OTP lên màn hình để test
            flash(f'[HỆ THỐNG EMAIL MÔ PHỎNG] Mã OTP khôi phục của bạn là: {otp}', 'success')
            
            # 4. Chuyển hướng sang trang nhập OTP
            return redirect(url_for('reset_password'))
        else:
            flash('Email này không tồn tại trong hệ thống!', 'danger')

    return render_template('forgot_password.html')

# ==========================================
# LUỒNG ĐẶT LẠI MẬT KHẨU (Nhập OTP)
# ==========================================
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    # Kiểm tra bảo mật: Tránh việc người dùng vào thẳng trang này khi chưa nhập email
    if 'reset_email' not in session:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        nhap_otp = request.form['otp']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        # Kiểm tra logic
        if nhap_otp != session.get('reset_otp'):
            flash('Mã OTP không chính xác!', 'danger')
        elif new_password != confirm_password:
            flash('Mật khẩu xác nhận không khớp!', 'danger')
        else:
            # Nếu mọi thứ hợp lệ -> Băm mật khẩu mới và lưu vào DB
            hashed_pw = generate_password_hash(new_password)
            
            conn = get_db()
            conn.execute('UPDATE taikhoan SET password_hash = ? WHERE email = ?', 
                         (hashed_pw, session['reset_email']))
            conn.commit()
            conn.close()

            # Xóa các biến tạm trong Session vì đã đổi xong
            session.pop('reset_email', None)
            session.pop('reset_otp', None)

            flash('Đổi mật khẩu thành công! Bạn có thể đăng nhập bằng mật khẩu mới.', 'success')
            return redirect(url_for('login'))

    return render_template('reset_password.html')

# ==========================================
# LUỒNG ĐĂNG KÝ (Trang riêng)
# ==========================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        ho_ten = request.form['hoTen']
        sdt = request.form['soDienThoai']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Kiểm tra mật khẩu xác nhận
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp!', 'danger')
            return redirect(url_for('register'))

        conn = get_db()
        # Kiểm tra xem username hoặc email đã tồn tại chưa
        user_exist = conn.execute('SELECT * FROM taikhoan WHERE username = ? OR email = ?', (username, email)).fetchone()

        if user_exist:
            flash('Tên đăng nhập hoặc Email đã được sử dụng!', 'danger')
        else:
            hashed_pw = generate_password_hash(password)
            conn.execute('''INSERT INTO taikhoan (username, password_hash, email, hoTen, soDienThoai) 
                            VALUES (?, ?, ?, ?, ?)''', 
                         (username, hashed_pw, email, ho_ten, sdt))
            conn.commit()
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            conn.close()
            return redirect(url_for('login')) # Chuyển hướng về trang đăng nhập
            
        conn.close()

    return render_template('register.html')
# Luồng Xem chi tiết & Tạo Đơn Hàng (Sequence Trang 13, 14)
# Luồng Xem chi tiết & Tạo Đơn Hàng
# Luồng Xem chi tiết, So sánh & Tạo Đơn Hàng
@app.route('/package/<int:id>', methods=['GET', 'POST'])
def detail(id):
    conn = get_db()
    # 1. Lấy thông tin gói hiện tại
    goi = conn.execute('SELECT * FROM goidichvu WHERE id = ?', (id,)).fetchone()
    
    # 2. Lấy danh sách CÁC GÓI KHÁC để làm menu so sánh
    cac_goi_khac = conn.execute('SELECT * FROM goidichvu WHERE id != ?', (id,)).fetchall()
    
    # 3. Kiểm tra xem khách có đang yêu cầu so sánh không (lấy ID gói thứ 2 từ URL)
    compare_id = request.args.get('compare_with')
    goi_so_sanh = None
    if compare_id:
        goi_so_sanh = conn.execute('SELECT * FROM goidichvu WHERE id = ?', (compare_id,)).fetchone()
    
    if request.method == 'POST':
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để đăng ký gói!', 'warning')
            return redirect(url_for('login'))
        
        from datetime import datetime
        thoi_gian_thuc = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        conn.execute('INSERT INTO donhang (user_id, goidichvu_id, tongTien, ngayTao) VALUES (?, ?, ?, ?)', 
                     (session['user_id'], id, goi['giaCuoc'], thoi_gian_thuc))
        conn.commit()
        
        flash(f'Đã tạo đơn hàng cho {goi["tenGoi"]}. Vui lòng thanh toán!', 'success')
        return redirect(url_for('profile')) # Đăng ký xong chuyển thẳng về Hồ sơ
        
    conn.close()
    return render_template('detail.html', goi=goi, cac_goi_khac=cac_goi_khac, goi_so_sanh=goi_so_sanh)
# ==========================================
# LUỒNG THÔNG TIN CÁ NHÂN & LỊCH SỬ GÓI
# ==========================================
@app.route('/profile')
def profile():
    # Kiểm tra bảo mật: Chưa đăng nhập thì không cho vào
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để xem thông tin tài khoản!', 'warning')
        return redirect(url_for('login'))

    conn = get_db()
    user_id = session['user_id']

    # 1. Lấy thông tin cá nhân của người dùng
    user_info = conn.execute('SELECT * FROM taikhoan WHERE id = ?', (user_id,)).fetchone()

    # 2. Lấy danh sách các gói dịch vụ đã đăng ký (Đơn hàng)
    query = '''
        SELECT dh.id, dh.ngayTao, dh.trangThai, dh.tongTien, g.tenGoi, g.maGoi
        FROM donhang dh
        JOIN goidichvu g ON dh.goidichvu_id = g.id
        WHERE dh.user_id = ?
        ORDER BY dh.ngayTao DESC
    '''
    packages = conn.execute(query, (user_id,)).fetchall()
    conn.close()

    return render_template('profile.html', user=user_info, packages=packages)
# ==========================================
# LUỒNG HỦY GÓI CƯỚC (Xóa đơn hàng)
# ==========================================
@app.route('/cancel_order/<int:order_id>')
def cancel_order(order_id):
    # Kiểm tra đã đăng nhập chưa
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db()
    # Xóa đơn hàng dựa vào ID (chỉ xóa đơn của đúng user đang đăng nhập để bảo mật)
    conn.execute('DELETE FROM donhang WHERE id = ? AND user_id = ?', (order_id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Đã hủy gói cước thành công!', 'success')
    return redirect(url_for('profile'))
# ==========================================
# LUỒNG NHÂN VIÊN: QUẢN LÝ KHÁCH HÀNG & ĐƠN HÀNG
# ==========================================
@app.route('/admin/users')
def admin_users():
    # Kiểm tra bảo mật: Chỉ nhân viên mới được vào
    if session.get('role') != 'nhanvien':
        flash('Bạn không có quyền truy cập trang này!', 'danger')
        return redirect(url_for('index'))

    conn = get_db()
    # 1. Lấy danh sách toàn bộ khách hàng
    khach_hang = conn.execute("SELECT * FROM taikhoan WHERE role = 'khachhang' ORDER BY id DESC").fetchall()
    
    # 2. Lấy danh sách toàn bộ đơn hàng của các khách hàng đó
    don_hang = conn.execute('''
        SELECT dh.id, dh.user_id, dh.ngayTao, dh.trangThai, g.tenGoi 
        FROM donhang dh 
        JOIN goidichvu g ON dh.goidichvu_id = g.id
    ''').fetchall()
    conn.close()

    return render_template('admin_users.html', khach_hang=khach_hang, don_hang=don_hang)

@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'nhanvien': return redirect(url_for('index'))
    
    conn = get_db()
    # Xóa toàn bộ đơn hàng của khách đó trước (để tránh lỗi khóa ngoại)
    conn.execute('DELETE FROM donhang WHERE user_id = ?', (user_id,))
    # Xóa khách hàng
    conn.execute('DELETE FROM taikhoan WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Đã xóa tài khoản khách hàng thành công!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/delete_order/<int:order_id>')
def admin_delete_order(order_id):
    if session.get('role') != 'nhanvien': return redirect(url_for('index'))
    
    conn = get_db()
    conn.execute('DELETE FROM donhang WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()
    flash('Đã hủy gói dịch vụ của khách!', 'success')
    return redirect(url_for('admin_users'))
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)