import os
import io
import base64
import pandas as pd
import qrcode
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///tokens.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    sector = db.Column(db.String(150), nullable=True)
    position = db.Column(db.String(150), nullable=True)
    token_balance = db.Column(db.Float, default=0.0)
    qr_code_data = db.Column(db.String(200), unique=True, nullable=True)
    must_change_password = db.Column(db.Boolean, default=True)

    @property
    def balance(self):
        return self.token_balance

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tokens_deducted = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    
    employee = db.relationship('User', foreign_keys=[employee_id], backref='transactions_received')
    merchant = db.relationship('User', foreign_keys=[merchant_id], backref='transactions_processed')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def generate_qr_image(data_string):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'merchant':
        return redirect(url_for('merchant_dashboard'))
    else:
        return redirect(url_for('employee_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user:
            if user.password is None:
                login_user(user)
                return redirect(url_for('setup_password'))
            if check_password_hash(user.password, password):
                login_user(user)
                if user.must_change_password:
                    return redirect(url_for('setup_password'))
                return redirect(url_for('index'))
        flash('Invalid username or password!', 'error')
    return render_template('login.html')

@app.route('/setup-password', methods=['GET', 'POST'])
@login_required
def setup_password():
    if request.method == 'POST':
        new_pass = request.form.get('new_password')
        current_user.password = generate_password_hash(new_pass)
        current_user.must_change_password = False
        db.session.commit()
        flash('Password created successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('login.html', setup_mode=True)
@app.route('/change-password')
@login_required
def change_password():
    return redirect(url_for('setup_password'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_single':
            role = request.form.get('role')
            username = request.form.get('username')
            full_name = request.form.get('full_name')
            sector = request.form.get('sector', '')
            position = request.form.get('position', '')
            
            if User.query.filter_by(username=username).first():
                flash('Username/ID already exists!', 'error')
            else:
                qr_data = f"EMP-{username}-{full_name}" if role == 'employee' else f"MERCH-{username}"
                new_user = User(
                    username=username,
                    role=role,
                    full_name=full_name,
                    sector=sector,
                    position=position,
                    qr_code_data=qr_data,
                    token_balance=0.0,
                    password=None # Force first time password setup
                )
                db.session.add(new_user)
                db.session.commit()
                flash(f'Successfully created {role}: {full_name}', 'success')

        elif action == 'bulk_upload':
            file = request.files.get('file')
            role_type = request.form.get('bulk_role')
            if file:
                df = pd.read_excel(file) if file.filename.endswith('.xlsx') else pd.read_csv(file)
                count = 0
                for _, row in df.iterrows():
                    username = str(row.get('username', row.iloc[0]))
                    full_name = str(row.get('full_name', row.iloc[1]))
                    sector = str(row.get('sector', row.iloc[2] if len(row) > 2 else ''))
                    position = str(row.get('position', row.iloc[3] if len(row) > 3 else ''))
                    
                    if not User.query.filter_by(username=username).first():
                        qr_data = f"EMP-{username}-{full_name}" if role_type == 'employee' else f"MERCH-{username}"
                        user = User(
                            username=username,
                            role=role_type,
                            full_name=full_name,
                            sector=sector,
                            position=position,
                            qr_code_data=qr_data,
                            token_balance=0.0,
                            password=None
                        )
                        db.session.add(user)
                        count += 1
                db.session.commit()
                flash(f'Successfully imported {count} records in bulk!', 'success')

        elif action == 'allocate_tokens':
            target = request.form.get('target_type')
            amount = float(request.form.get('amount', 0))
            if target == 'all_employees':
                employees = User.query.filter_by(role='employee').all()
                for e in employees:
                    e.token_balance += amount
            elif target == 'sector':
                sector_name = request.form.get('sector_name')
                employees = User.query.filter_by(role='employee', sector=sector_name).all()
                for e in employees:
                    e.token_balance += amount
            db.session.commit()
            flash('Tokens allocated successfully!', 'success')

        elif action == 'delete_user':
            user_id = request.form.get('user_id')
            user_to_delete = db.session.get(User, int(user_id))
            if user_to_delete and user_to_delete.role != 'admin':
                db.session.delete(user_to_delete)
                db.session.commit()
                flash('User removed successfully!', 'success')

        elif action == 'delete_bulk':
            role_to_delete = request.form.get('bulk_delete_role')
            users = User.query.filter_by(role=role_to_delete).all()
            for u in users:
                db.session.delete(u)
            db.session.commit()
            flash(f'All {role_to_delete} accounts removed successfully!', 'success')

        elif action == 'reset_password':
            user_id = request.form.get('user_id')
            user_to_reset = db.session.get(User, int(user_id))
            if user_to_reset:
                user_to_reset.password = None
                user_to_reset.must_change_password = True
                db.session.commit()
                flash(f"Password reset for {user_to_reset.full_name}. They can now set a new password upon login.", 'success')

        elif action == 'reset_all_passwords':
            role_to_reset = request.form.get('bulk_password_role')
            users = User.query.filter_by(role=role_to_reset).all()
            for u in users:
                u.password = None
                u.must_change_password = True
            db.session.commit()
            flash(f"All {role_to_reset} passwords reset successfully!", 'success')

    # Queries
    employees = User.query.filter_by(role='employee').all()
    merchants = User.query.filter_by(role='merchant').all()
    sectors = db.session.query(User.sector).filter(User.sector != '').distinct().all()
    sectors = [s[0] for s in sectors if s[0] and s[0] != 'nan']

    # Filters
    selected_merchant_id = request.args.get('merchant_id', '')
    selected_sector = request.args.get('sector_filter', '')
    selected_period = request.args.get('period_filter', '')
    selected_date = request.args.get('report_date', '')

    tx_query = Transaction.query
    if selected_merchant_id:
        tx_query = tx_query.filter_by(merchant_id=int(selected_merchant_id))
    if selected_sector:
        tx_query = tx_query.join(User, Transaction.employee_id == User.id).filter(User.sector == selected_sector)
    if selected_date:
        if selected_period == 'daily':
            tx_query = tx_query.filter(db.func.date(Transaction.timestamp) == selected_date)
        elif selected_period == 'monthly':
            tx_query = tx_query.filter(db.func.strftime('%Y-%m', Transaction.timestamp) == selected_date)

    transactions = tx_query.order_by(Transaction.timestamp.desc()).all()
    total_tokens_redeemed = sum(tx.tokens_deducted for tx in transactions)

    return render_template(
        'admin_dashboard.html',
        employees=employees,
        merchants=merchants,
        sectors=sectors,
        transactions=transactions,
        selected_merchant_id=selected_merchant_id,
        selected_sector=selected_sector,
        selected_period=selected_period,
        selected_date=selected_date,
        total_tokens_redeemed=total_tokens_redeemed
    )

@app.route('/print-qr/<int:user_id>')
@login_required
def print_qr(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return "User not found", 404
    qr_img = generate_qr_image(user.qr_code_data)
    return render_template('print_single_qr.html', user=user, qr_img=qr_img)

@app.route('/print-bulk-qr')
@login_required
def print_bulk_qr():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    sector = request.args.get('sector', '')
    query = User.query.filter_by(role='employee')
    if sector and sector != 'All':
        query = query.filter_by(sector=sector)
        sector_title = sector
    else:
        sector_title = "All Sectors"
    employees = query.all()
    
    emp_data = []
    for emp in employees:
        emp_data.append({
            'full_name': emp.full_name,
            'username': emp.username,
            'sector': emp.sector or 'General',
            'position': emp.position or 'Staff',
            'qr_img': generate_qr_image(emp.qr_code_data)
        })
    return render_template('print_bulk_qr.html', employees=emp_data, sector=sector_title)

@app.route('/merchant', methods=['GET', 'POST'])
@login_required
def merchant_dashboard():
    if current_user.role != 'merchant':
        return redirect(url_for('index'))
    
    # Calculate daily and total collections for this merchant
    today_str = pd.Timestamp.now().strftime('%Y-%m-%d')
    
    all_txs = Transaction.query.filter_by(merchant_id=current_user.id).order_by(Transaction.timestamp.desc()).all()
    total_collected = sum(tx.tokens_deducted for tx in all_txs)
    
    daily_collected = sum(
        tx.tokens_deducted for tx in all_txs 
        if str(tx.timestamp).startswith(today_str)
    )
    
    return render_template(
        'merchant_scan.html', 
        transactions=all_txs,
        total_collected=total_collected,
        daily_collected=daily_collected
    )
@app.route('/api/deduct', methods=['POST'])
@login_required
def deduct_tokens():
    if current_user.role != 'merchant':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    qr_code = data.get('qr_code')
    amount = float(data.get('amount', 1.0))
    
    employee = User.query.filter_by(qr_code_data=qr_code, role='employee').first()
    if not employee:
        return jsonify({'success': False, 'message': 'Invalid Employee QR Code!'})
    
    if employee.token_balance < amount:
        return jsonify({'success': False, 'message': f'Insufficient Balance! Available: {employee.token_balance} tokens.'})
    
    employee.token_balance -= amount
    tx = Transaction(employee_id=employee.id, merchant_id=current_user.id, tokens_deducted=amount)
    db.session.add(tx)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Successfully deducted {amount} tokens!',
        'employee_name': employee.full_name,
        'new_balance': employee.token_balance
    })

@app.route('/employee')
@login_required
def employee_dashboard():
    if current_user.role != 'employee':
        return redirect(url_for('index'))
    qr_img = generate_qr_image(current_user.qr_code_data) if current_user.qr_code_data else ""
    transactions = Transaction.query.filter_by(employee_id=current_user.id).order_by(Transaction.timestamp.desc()).all()
    return render_template('employee_portal.html', user=current_user, qr_img=qr_img, transactions=transactions)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password=generate_password_hash('Admin123!'),
                role='admin',
                full_name='System Administrator',
                must_change_password=False
            )
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, host='0.0.0.0', port=5000)