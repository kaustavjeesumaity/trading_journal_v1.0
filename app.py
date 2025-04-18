from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_uploads import UploadSet, configure_uploads, IMAGES
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trades.db'
app.config['UPLOADED_PHOTOS_DEST'] = 'uploads'
app.secret_key = 'your-secret-key'

db = SQLAlchemy(app)
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)

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
    entry_price  = db.Column(db.Float)
    exit_price = db.Column(db.Float)
    quantity = db.Column(db.Float)

    @property
    def status(self):
        return 'CLOSED' if self.end_time else 'OPEN'

    @property
    def net_pnl(self):
        if self.gross_pnl is not None and self.charges is not None:
            return self.gross_pnl - self.charges
        return 0
    
    
class TradeImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100))
    trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/uploads/<filename>')
def get_file(filename):
    return send_from_directory(app.config['UPLOADED_PHOTOS_DEST'], filename)


@app.route('/')
def index():
    trades = Trade.query.order_by(Trade.start_time.desc()).all()
    return render_template('index.html', trades=trades)

@app.route('/trade/<int:id>')
def view_trade(id):
    trade = Trade.query.get_or_404(id)
    return render_template('trade_detail.html', trade=trade)

@app.route('/add', methods=['GET', 'POST'])
def add_trade():
    if request.method == 'POST':
        try:
            end_time = request.form.get('end_time')
            is_closed = bool(end_time)
            
            # Validate closed trade requirements
            if is_closed:
                if not all([request.form.get('gross_pnl'), request.form.get('charges')]):
                    flash('Gross P&L and Charges are required for closed trades', 'error')
                    return render_template('add_trade.html')

            trade = Trade(
                start_time=datetime.fromisoformat(request.form['start_time']),
                symbol=request.form['symbol'],
                gross_pnl=float(request.form['gross_pnl']) if request.form.get('gross_pnl') else None,
                charges=float(request.form['charges']) if request.form.get('charges') else None,
                entry_price=float(request.form.get('entry_price', 0)),
                exit_price=float(request.form.get('exit_price', 0)),
                quantity=float(request.form.get('quantity', 0)),
                notes=request.form.get('notes', ''),
                end_time=datetime.fromisoformat(end_time) if end_time else None
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
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('add_trade.html')

# Similar modifications to edit_trade route

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_trade(id):
    trade = Trade.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            end_time = request.form.get('end_time')
            is_closed = bool(end_time)
            # Validate closed trade requirements
            if is_closed:
                print([request.form.get('gross_pnl'), request.form.get('charges')])
                if not all([request.form.get('gross_pnl'), request.form.get('charges')]):
                    print('Here')
                    flash('Gross P&L and Charges are required for closed trades', 'error')
                    return render_template('edit_trade.html', trade=trade)

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
            
            trade.entry_price = float(request.form['entry_price'])
            trade.exit_price = float(request.form['exit_price'])
            trade.quantity = float(request.form['quantity'])
            # Handle new images
            new_images = request.files.getlist('images')
            for file in new_images:
                if file.filename != '':
                    filename = photos.save(file)
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
            return redirect(url_for('view_trade', id=trade.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating trade: {str(e)}', 'error')
    
    # GET request - show edit form
    return render_template('edit_trade.html', 
                         trade=trade,
                         images=trade.images)


# Add this at the top after creating Flask app  # Required for flash messages

# Update delete route
@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete_trade(id):
    trade = Trade.query.get_or_404(id)
    
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
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting trade: {str(e)}', 'error')
            return redirect(url_for('confirm_delete', id=id))
    
    # GET request shows confirmation page
    return render_template('confirm_delete.html', trade=trade)

@app.route('/chart-data')
def chart_data():
    trades = Trade.query.order_by(Trade.start_time).all()
    dates = []
    cumulative_pnl = []
    running_total = 0
    
    for trade in trades:
        if trade.status == 'CLOSED':
            dates.append(trade.start_time.strftime('%Y-%m-%d'))
            running_total += trade.net_pnl
            cumulative_pnl.append(round(running_total, 2))
    
    return jsonify({
        'dates': dates,
        'cumulative_pnl': cumulative_pnl
    })

if __name__ == '__main__':
    app.run(debug=True)