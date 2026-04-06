from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'khoa_bao_mat_he_thong_dich_vu'

def cleanup_expired_orders():
    conn = get_db()
    # Lấy tất cả đơn hàng đang 'Chờ thanh toán'
    orders = conn.execute("SELECT id, ngayTao FROM donhang WHERE trangThai = 'Chờ thanh toán'").fetchall()
    
    from datetime import datetime
    bay_gio = datetime.now()
    
    for order in orders:
        try:
            # Chuyển chuỗi ngàyTao (định dạng dd/mm/yyyy HH:MM:SS) về đối tượng datetime
            ngay_tao_dt = datetime.strptime(order['ngayTao'], "%d/%m/%Y %H:%M:%S")
            
            # Tính khoảng cách thời gian (giây)
            khoang_cach = (bay_gio - ngay_tao_dt).total_seconds()
            
            # Nếu quá 300 giây (5 phút)
            if khoang_cach > 300:
                conn.execute("UPDATE donhang SET trangThai = 'Giao dịch thất bại' WHERE id = ?", (order['id'],))
        except:
            pass # Bỏ qua nếu định dạng ngày cũ không khớp
            
    conn.commit()
    conn.close()

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
    # Bảng Lưu trữ tin nhắn Hỗ trợ / Chat (Từ lược đồ PhieuHoTro)
    c.execute('''CREATE TABLE IF NOT EXISTS ho_tro 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  nguoi_gui TEXT, 
                  noi_dung TEXT, 
                  thoi_gian DATETIME,
                  FOREIGN KEY(user_id) REFERENCES taikhoan(id))''')
                  
    # Tạo bảng goidichvu và donhang 
    c.execute('''CREATE TABLE IF NOT EXISTS goidichvu 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  maGoi TEXT UNIQUE NOT NULL, 
                  tenGoi TEXT NOT NULL, 
                  giaCuoc REAL NOT NULL, 
                  moTa TEXT,
                  thoiHan INTEGER DEFAULT 30)''')
    c.execute('''CREATE TABLE IF NOT EXISTS donhang 
              (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              user_id INTEGER, goidichvu_id INTEGER, 
              ngayTao DATETIME DEFAULT CURRENT_TIMESTAMP, 
              trangThai TEXT DEFAULT 'Chờ thanh toán', 
              tongTien REAL, 
              FOREIGN KEY(user_id) REFERENCES taikhoan(id), 
              FOREIGN KEY(goidichvu_id) REFERENCES goidichvu(id))''')

    # TỰ ĐỘNG TẠO TÀI KHOẢN NHÂN VIÊN MẶC ĐỊNH
    admin_exist = c.execute("SELECT * FROM taikhoan WHERE role = 'nhanvien'").fetchone()
    if not admin_exist:
        hashed_pw = generate_password_hash("123456") # Mật khẩu mặc định là 123456
        c.execute("INSERT INTO taikhoan (username, password_hash, hoTen, role) VALUES (?, ?, ?, ?)", 
                  ('admin', hashed_pw, 'Quản Trị Viên', 'nhanvien'))
    # TỰ ĐỘNG TẠO TÀI KHOẢN SIÊU QUẢN TRỊ VIÊN (Super Admin)
    superadmin_exist = c.execute("SELECT * FROM taikhoan WHERE username = 'AdminOffical'").fetchone()
    if not superadmin_exist:
        hashed_pw = generate_password_hash("123456") 
        c.execute("INSERT INTO taikhoan (username, password_hash, hoTen, role) VALUES (?, ?, ?, ?)", 
                  ('AdminOffical', hashed_pw, 'Tổng Quản Trị Hệ Thống', 'quantrivien'))

    # Dữ liệu mẫu
    if c.execute('SELECT COUNT(*) FROM goidichvu').fetchone()[0] == 0:
        c.executemany('INSERT INTO goidichvu (maGoi, tenGoi, giaCuoc, moTa, thoiHan) VALUES (?, ?, ?, ?, ?)', 
                      [('SD_90', 'SD90', 90000, '45GB/Tháng. Mỗi ngày cộng 1,5GB.', 30), 
                       ('SD_120', 'SD120', 120000, '60GB /tháng. Cộng 2GB mỗi ngày.', 30), 
                       ('SD_135', 'SD135', 135000, '150GB /tháng. Cộng 5GB mỗi ngày.', 30)])
        
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
            if user['role'] == 'quantrivien':
                return redirect(url_for('superadmin_dashboard')) # Chuyển đến trang Cấp cao
            elif user['role'] == 'nhanvien':
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
    cleanup_expired_orders()
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
    cleanup_expired_orders()
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

@app.route('/admin/confirm_order/<int:order_id>')
def admin_confirm_order(order_id):
    # Kiểm tra quyền nhân viên
    if session.get('role') != 'nhanvien': return redirect(url_for('index'))
    
    conn = get_db()
    # Lệnh UPDATE để đổi trạng thái đơn hàng
    conn.execute("UPDATE donhang SET trangThai = 'Đang hoạt động' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    
    flash('Đã xác nhận thanh toán và kích hoạt gói cước cho khách!', 'success')
    return redirect(url_for('admin_users'))
# ==========================================
# LUỒNG CHAT KHÁCH HÀNG (Gửi khiếu nại)
# ==========================================
@app.route('/support', methods=['GET', 'POST'])
def support():
    # Chỉ khách hàng mới được dùng trang này
    if 'user_id' not in session or session.get('role') == 'nhanvien':
        return redirect(url_for('login'))
    
    conn = get_db()
    if request.method == 'POST':
        noi_dung = request.form['noi_dung']
        if noi_dung.strip():
            from datetime import datetime
            thoi_gian_thuc = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            # Lưu tin nhắn với người gửi là 'khachhang'
            conn.execute('INSERT INTO ho_tro (user_id, nguoi_gui, noi_dung, thoi_gian) VALUES (?, ?, ?, ?)',
                         (session['user_id'], 'khachhang', noi_dung, thoi_gian_thuc))
            conn.commit()
            return redirect(url_for('support'))
            
    # Lấy toàn bộ lịch sử chat của khách hàng này
    messages = conn.execute('SELECT * FROM ho_tro WHERE user_id = ? ORDER BY id ASC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('support.html', messages=messages)

# ==========================================
# LUỒNG CHAT NHÂN VIÊN (Quản lý khiếu nại)
# ==========================================
@app.route('/admin/support')
def admin_support():
    if session.get('role') != 'nhanvien': return redirect(url_for('index'))
    conn = get_db()
    # Lấy danh sách các khách hàng đã từng nhắn tin
    khach_hang_chat = conn.execute('''
        SELECT DISTINCT t.id, t.hoTen, t.username, t.soDienThoai
        FROM taikhoan t JOIN ho_tro h ON t.id = h.user_id
    ''').fetchall()
    conn.close()
    return render_template('admin_support.html', khach_hang=khach_hang_chat)

@app.route('/admin/support/<int:user_id>', methods=['GET', 'POST'])
def admin_chat(user_id):
    if session.get('role') != 'nhanvien': return redirect(url_for('index'))
    conn = get_db()
    
    if request.method == 'POST':
        noi_dung = request.form['noi_dung']
        if noi_dung.strip():
            from datetime import datetime
            thoi_gian_thuc = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            # Lưu tin nhắn phản hồi với người gửi là 'nhanvien'
            conn.execute('INSERT INTO ho_tro (user_id, nguoi_gui, noi_dung, thoi_gian) VALUES (?, ?, ?, ?)',
                         (user_id, 'nhanvien', noi_dung, thoi_gian_thuc))
            conn.commit()
            return redirect(url_for('admin_chat', user_id=user_id))
            
    # Lấy lịch sử chat của khách hàng được chọn
    messages = conn.execute('SELECT * FROM ho_tro WHERE user_id = ? ORDER BY id ASC', (user_id,)).fetchall()
    khach_hang = conn.execute('SELECT * FROM taikhoan WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return render_template('admin_chat.html', messages=messages, khach_hang=khach_hang)
# ==========================================
# LUỒNG QUẢN TRỊ VIÊN CẤP CAO (Super Admin)
# ==========================================
@app.route('/superadmin')
def superadmin_dashboard():
    if session.get('role') != 'quantrivien': return redirect(url_for('login'))
    conn = get_db()
    nhan_vien = conn.execute("SELECT * FROM taikhoan WHERE role = 'nhanvien'").fetchall()
    # LẤY THÊM DÒNG NÀY:
    goi_dich_vu = conn.execute("SELECT * FROM goidichvu").fetchall() 
    conn.close()
    return render_template('superadmin.html', nhan_vien=nhan_vien, goi_dich_vu=goi_dich_vu)

@app.route('/superadmin/add_employee', methods=['POST'])
def add_employee():
    if session.get('role') != 'quantrivien': return redirect(url_for('login'))
    
    username = request.form['username']
    password = request.form['password']
    hoTen = request.form['hoTen']
    
    conn = get_db()
    # Kiểm tra xem tên đăng nhập đã trùng chưa
    user_exist = conn.execute("SELECT * FROM taikhoan WHERE username = ?", (username,)).fetchone()
    
    if user_exist:
        flash('Tên đăng nhập này đã tồn tại, vui lòng chọn tên khác!', 'danger')
    else:
        # Băm mật khẩu và lưu nhân viên mới
        hashed_pw = generate_password_hash(password)
        conn.execute("INSERT INTO taikhoan (username, password_hash, hoTen, role) VALUES (?, ?, ?, ?)",
                     (username, hashed_pw, hoTen, 'nhanvien'))
        conn.commit()
        flash(f'Đã tạo tài khoản nhân viên cho {hoTen} thành công!', 'success')
        
    conn.close()
    return redirect(url_for('superadmin_dashboard'))

@app.route('/superadmin/delete_employee/<int:emp_id>')
def delete_employee(emp_id):
    if session.get('role') != 'quantrivien': return redirect(url_for('login'))
    
    conn = get_db()
    conn.execute("DELETE FROM taikhoan WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()
    flash('Đã xóa tài khoản nhân viên thành công!', 'success')
    return redirect(url_for('superadmin_dashboard'))
# ==========================================
# QUẢN TRỊ VIÊN: QUẢN LÝ GÓI DỊCH VỤ (CRUD)
# ==========================================

# 1. Thêm gói mới
@app.route('/superadmin/add_package', methods=['POST'])
def admin_add_package():
    if session.get('role') != 'quantrivien': return redirect(url_for('login'))
    
    tenGoi = request.form['tenGoi']
    maGoi = request.form['maGoi']
    moTa = request.form['moTa']
    giaCuoc = request.form['giaCuoc']
    thoiHan = request.form['thoiHan'] # LẤY THỜI HẠN
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO goidichvu (maGoi, tenGoi, giaCuoc, moTa, thoiHan) VALUES (?, ?, ?, ?, ?)',
                     (maGoi, tenGoi, giaCuoc, moTa, thoiHan))
        conn.commit()
        flash('Đã thêm gói dịch vụ mới thành công!', 'success')
    except:
        flash('Lỗi: Mã gói này đã tồn tại!', 'danger')
    conn.close()
    return redirect(url_for('superadmin_dashboard'))

# 2. Xóa gói
@app.route('/superadmin/delete_package/<int:package_id>')
def admin_delete_package(package_id):
    if session.get('role') != 'quantrivien': return redirect(url_for('login'))
    
    conn = get_db()
    # Kiểm tra xem có đơn hàng nào đang dùng gói này không để tránh lỗi dữ liệu
    check = conn.execute('SELECT COUNT(*) FROM donhang WHERE goidichvu_id = ?', (package_id,)).fetchone()[0]
    if check > 0:
        flash('Không thể xóa gói này vì đã có khách hàng đăng ký!', 'danger')
    else:
        conn.execute('DELETE FROM goidichvu WHERE id = ?', (package_id,))
        conn.commit()
        flash('Đã xóa gói dịch vụ!', 'success')
    conn.close()
    return redirect(url_for('superadmin_dashboard'))

# 3. Trang Chỉnh sửa gói (Giao diện sửa)
@app.route('/superadmin/edit_package/<int:package_id>', methods=['GET', 'POST'])
def admin_edit_package(package_id):
    if session.get('role') != 'quantrivien': return redirect(url_for('login'))
    
    conn = get_db()
    if request.method == 'POST':
        tenGoi = request.form['tenGoi']
        maGoi = request.form['maGoi']
        moTa = request.form['moTa']
        giaCuoc = request.form['giaCuoc']
        thoiHan = request.form['thoiHan'] # LẤY THỜI HẠN
        
        conn.execute('UPDATE goidichvu SET tenGoi=?, maGoi=?, giaCuoc=?, moTa=?, thoiHan=? WHERE id=?',
                     (tenGoi, maGoi, giaCuoc, moTa, thoiHan, package_id))
        conn.commit()
        conn.close()
        flash('Đã cập nhật thông tin gói cước!', 'success')
        return redirect(url_for('superadmin_dashboard'))
    
    package = conn.execute('SELECT * FROM goidichvu WHERE id = ?', (package_id,)).fetchone()
    conn.close()
    return render_template('edit_package.html', package=package)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Thêm host='0.0.0.0' để cho phép các máy khác trong mạng truy cập
    app.run(host='0.0.0.0', debug=True, port=5000)