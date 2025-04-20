from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_uploads import UploadSet, configure_uploads, IMAGES
from datetime import datetime
import os
import pandas as pd
import json
from io import StringIO

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://trade_user:strong_password@localhost/trade_journal'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOADED_PHOTOS_DEST'] = 'uploads'
app.secret_key = 'your-secret-key'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci'
    }
}
db = SQLAlchemy(app)
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(10), nullable=False)  # 'MT5' or 'Manual'
    account_number = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    symbol = db.Column(db.String(20), nullable=False)
    gross_pnl = db.Column(db.Float)
    charges = db.Column(db.Float)
    notes = db.Column(db.Text)
    images = db.relationship('TradeImage', backref='trade', 
                            cascade='all, delete-orphan',
                            lazy=True)
    entry_price = db.Column(db.DECIMAL(20, 5))
    exit_price = db.Column(db.DECIMAL(20, 5))
    quantity = db.Column(db.DECIMAL(20, 2))
    platform = db.Column(db.String(10), nullable=False)  # 'MT5' or 'Manual'
    account_number = db.Column(db.String(20), nullable=False)

    @property
    def status(self):
        return 'CLOSED' if self.end_time else 'OPEN'

    @property
    def net_pnl(self):
        if self.gross_pnl is not None and self.charges is not None:
            return self.gross_pnl - self.charges
        return None
    
    
class TradeImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100))
    trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=False)

with app.app_context():
    db.create_all()


# Add to app.py
@app.route('/add-account', methods=['GET', 'POST'])
def add_account():
    current_filter = get_current_filter()
    if request.method == 'POST':
        try:
            platform = request.form['platform'].upper()
            account_number = request.form['account_number']
            
            # Validate unique account per platform
            if Account.query.filter_by(platform=platform, account_number=account_number).first():
                flash('Account already exists for this platform', 'error')
                return redirect(url_for('add_account'))
            
            account = Account(platform=platform, account_number=account_number)
            db.session.add(account)
            db.session.commit()
            flash('Account created successfully', 'success')
            return redirect(url_for('index',platform = platform, account=account_number))
            
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'error')
    
    return render_template('add_account.html',current_filter=current_filter)

@app.route('/get-accounts/<platform>')
def get_accounts(platform):
    accounts = Account.query.filter_by(platform=platform.upper()).all()
    return jsonify([{'id': a.id, 'account_number': a.account_number} for a in accounts])

@app.route('/bulk-import', methods=['GET', 'POST'])
def bulk_import():
    current_filter = get_current_filter()
    if request.method == 'POST':
        try:
            account_number = request.form['account_number']
            csv_file = request.files['csv_file']
            df = pd.read_csv(StringIO(csv_file.read().decode('utf-8')))
            
            # Filter and preprocess
            df = df[df['type'].isin([0, 1])]  # Only include types 0 and 1
            df['time'] = pd.to_datetime(df['time'])
            
            # Group by position_id and type
            grouped = df.groupby(['position_id', 'type'])
            
            # Aggregate metrics
            aggregated = grouped.agg({
                'time': ['min', 'max'],
                'volume': 'sum',
                'price': 'mean',
                'swap': 'sum',
                'profit': 'sum',
                'fee': 'sum',
                'symbol': 'first'
            }).reset_index()
            
            # Create trades
            trades = []
            for position_id in df['position_id'].unique():
                position_data = aggregated[aggregated['position_id'] == position_id]
                
                # Get open/close data
                open_data = position_data[position_data['type'] == 0]
                close_data = position_data[position_data['type'] == 1]
                
                # Base metrics
                entry_price = open_data['price'].values[0][0] if not open_data.empty else None
                exit_price = close_data['price'].values[0][0] if not close_data.empty else None
                quantity = open_data['volume'].values[0][0]
                
                # Time calculations
                start_time = open_data['time']['min'].min() if not open_data.empty else None
                end_time = close_data['time']['max'].max() if not close_data.empty else None
                
                # P&L calculations
                gross_pnl = (open_data['profit'].sum() + close_data['profit'].sum())['sum']
                charges = (open_data['swap'].sum() + open_data['fee'].sum() + 
                          close_data['swap'].sum() + close_data['fee'].sum())['sum']
                if entry_price:
                    print('adsf')
                    trade = Trade(
                        symbol=open_data['symbol'].iloc[0].values[0],
                        start_time=start_time.to_pydatetime(),
                        end_time=end_time.to_pydatetime() if end_time else None,
                        entry_price=round(entry_price, 5),
                        exit_price=round(exit_price, 5) if exit_price else None,
                        quantity=round(quantity, 2),
                        gross_pnl=round(gross_pnl, 2),
                        charges=round(charges, 2),
                        notes=f"Bulk import {position_id}",
                        platform = 'MT5',
                        account_number = account_number
                    )
                    trades.append(trade)
            
            db.session.bulk_save_objects(trades)
            db.session.commit()
            flash(f'Imported {len(trades)} trades successfully', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'error')
            print(e)
            
        return redirect(url_for('index',**current_filter))
    mt5_accounts = Account.query.filter_by(platform='MT5').order_by(Account.account_number).all()
    return render_template('bulk_import.html',mt5_accounts=mt5_accounts,current_filter=current_filter)


@app.route('/uploads/<filename>')
def get_file(filename):
    return send_from_directory(app.config['UPLOADED_PHOTOS_DEST'], filename)


def get_current_filter():
    return {
        'platform': request.args.get('platform'),
        'account': request.args.get('account')
    }

@app.route('/')
def index():
    
    current_filter = get_current_filter()
    print(f'cur : {current_filter}')
    
    # Only show trades if both platform and account are selected
    if current_filter['platform'] and current_filter['account']:
        trades = Trade.query.filter_by(
            platform=current_filter['platform'],
            account_number=current_filter['account']
        ).order_by(Trade.start_time.desc()).all()
    else:
        trades = []
    
    return render_template('index.html',
                         trades=trades,
                         current_filter=current_filter)

@app.route('/trade/<int:id>')
def view_trade(id):
    current_filter = get_current_filter()
    print(current_filter)
    trade = Trade.query.get_or_404(id)
    return render_template('trade_detail.html', trade=trade, current_filter = current_filter)

@app.route('/add', methods=['GET', 'POST'])
def add_trade():
    current_filter = get_current_filter()
    if request.method == 'POST':
        try:
            print(f'add form : {request.form}')
            end_time = request.form.get('end_time')
            is_closed = bool(end_time)
            print(f'account : {request.form.get('account_number')}')
            # Validate closed trade requirements
            if is_closed:
                if not all([request.form.get('gross_pnl'), request.form.get('charges')]):
                    flash('Gross P&L and Charges are required for closed trades', 'error')
                    return render_template('add_trade.html',current_filter=current_filter)
            print(f'{request.form.get('exit_price', 0) = }')
            print(f'{float(request.form['gross_pnl']) if request.form.get('gross_pnl') else None = }')
            trade = Trade(
                start_time=datetime.fromisoformat(request.form['start_time']),
                symbol=request.form['symbol'],
                gross_pnl=float(request.form['gross_pnl']) if request.form.get('gross_pnl') else None,
                charges=float(request.form['charges']) if request.form.get('charges') else None,
                entry_price=float(request.form['entry_price']) if request.form.get('entry_price') else None,
                exit_price=float(request.form['exit_price']) if request.form.get('exit_price') else None,
                quantity=float(request.form['quantity']) if request.form.get('quantity') else None,
                notes=request.form.get('notes', ''),
                end_time=datetime.fromisoformat(end_time) if end_time else None,
                account_number = request.form.get('account_number'),
                platform = request.form.get('platform').upper()
            )
            
            db.session.add(trade)
            db.session.commit()

            # Handle image uploads
            for file in request.files.getlist('images'):
                if file.filename != '':
                    filename = photos.save(file)
                    image = TradeImage(filename=filename, trade_id=trade.id)
                    db.session.add(image)
            
            db.session.commit()
            flash('Trade added successfully', 'success')
            return redirect(url_for('index',**current_filter))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('add_trade.html',current_filter=current_filter)

# Similar modifications to edit_trade route

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_trade(id):
    current_filter = get_current_filter()
    trade = Trade.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            print(f'edit form : {request.form}')
            end_time = request.form.get('end_time')
            is_closed = bool(end_time)
            # Validate closed trade requirements
            if is_closed:
                print([request.form.get('gross_pnl'), request.form.get('charges')])
                if not all([request.form.get('gross_pnl'), request.form.get('charges')]):
                    print('Here')
                    flash('Gross P&L and Charges are required for closed trades', 'error')
                    return render_template('edit_trade.html', trade=trade,current_filter=current_filter)

            # Update fields
            trade.gross_pnl = float(request.form['gross_pnl']) if request.form.get('gross_pnl') else None
            trade.charges = float(request.form['charges']) if request.form.get('charges') else None
            # Update basic fields
            trade.start_time = datetime.fromisoformat(request.form['start_time'])
            trade.symbol = request.form['symbol']
            trade.notes = request.form.get('notes', '')
            
            # Handle end time (optional)
            if request.form.get('end_time'):
                trade.end_time = datetime.fromisoformat(request.form['end_time'])
            else:
                trade.end_time = None
            
            trade.entry_price=float(request.form['entry_price']) if request.form.get('entry_price') else None
            trade.exit_price=float(request.form['exit_price']) if request.form.get('exit_price') else None
            trade.quantity=float(request.form['quantity']) if request.form.get('quantity') else None
            # Handle new images
            new_images = request.files.getlist('images')
            print(new_images)
            for file in new_images:
                if file.filename != '':
                    filename = photos.save(file)
                    print(filename)
                    image = TradeImage(filename=filename, trade_id=trade.id)
                    db.session.add(image)

            # Handle image deletions
            delete_images = request.form.getlist('delete_images')
            for image_id in delete_images:
                image = TradeImage.query.get(image_id)
                if image and image.trade_id == trade.id:
                    # Delete file from filesystem
                    try:
                        os.remove(os.path.join(app.config['UPLOADED_PHOTOS_DEST'], image.filename))
                    except Exception as e:
                        app.logger.error(f"Error deleting file {image.filename}: {str(e)}")
                    # Remove from database
                    db.session.delete(image)

            db.session.commit()
            flash('Trade updated successfully', 'success')
            return redirect(url_for('view_trade', id=trade.id,**current_filter))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating trade: {str(e)}', 'error')
    
    # GET request - show edit form
    return render_template('edit_trade.html', 
                         trade=trade,
                         images=trade.images,
                         current_filter=current_filter)


# Add this at the top after creating Flask app  # Required for flash messages

# Update delete route
@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete_trade(id):
    trade = Trade.query.get_or_404(id)
    current_filter = get_current_filter()
    if request.method == 'POST':
        try:
            # Delete associated images first
            for image in trade.images:
                try:
                    file_path = os.path.join(app.config['UPLOADED_PHOTOS_DEST'], image.filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    app.logger.error(f"Error deleting file {image.filename}: {str(e)}")
                db.session.delete(image)
            
            # Delete the trade
            db.session.delete(trade)
            db.session.commit()
            flash('Trade and all associated images deleted successfully', 'success')
            return redirect(url_for('index',**current_filter))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting trade: {str(e)}', 'error')
            return redirect(url_for('confirm_delete', id=id))
    
    # GET request shows confirmation page
    return render_template('confirm_delete.html', trade=trade,current_filter=current_filter)

@app.route('/chart-data',methods=['GET', 'POST'])
def chart_data():
    current_filter = get_current_filter()
    if not all(current_filter.values()):
        return jsonify({})
    print(current_filter)
    trades = Trade.query.filter_by(
        platform=current_filter['platform'],
        account_number=current_filter['account']
    ).order_by(Trade.start_time).all()
    dates = []
    cumulative_pnl = []
    running_total = 0
    
    for trade in trades:
        if trade.status == 'CLOSED':
            dates.append(trade.start_time.strftime('%Y-%m-%d'))
            running_total += trade.net_pnl
            cumulative_pnl.append(round(running_total, 2))
    
    return jsonify({
        'labels': dates,
        'datasets': [{
            'label': 'Cumulative Net P&L',
            'data': cumulative_pnl,
            'borderColor': '#4CAF50',
            'tension': 0.1
        }]
    })

if __name__ == '__main__':
    app.run(debug=True)