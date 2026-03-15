from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(UserMixin, db.Model):
    """Admin user for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Staff(db.Model):
    """Child care staff member."""
    __tablename__ = 'staff'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    hire_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    schedule_assignments = db.relationship('ScheduleAssignment', back_populates='staff', lazy='dynamic')
    checklist_completions = db.relationship('ChecklistCompletion', back_populates='staff', lazy='dynamic')
    
    def __repr__(self):
        return f'<Staff {self.full_name}>'


class ScheduleAssignment(db.Model):
    """Staff assignment to a shift on a specific date."""
    __tablename__ = 'schedule_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    shift_type = db.Column(db.String(20), nullable=False)  # 'before' or 'after'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    staff = db.relationship('Staff', back_populates='schedule_assignments')
    
    # Ensure no double-booking
    __table_args__ = (
        db.UniqueConstraint('staff_id', 'date', 'shift_type', name='uix_schedule'),
    )
    
    def __repr__(self):
        return f'<ScheduleAssignment {self.staff.full_name} {self.date} {self.shift_type}>'


class ChecklistItem(db.Model):
    """Licensing requirement checklist item."""
    __tablename__ = 'checklist_items'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)  # e.g., 'training', 'documentation'
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    required_for = db.Column(db.String(50), default='all')  # 'all', 'before_care', 'after_care'
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    completions = db.relationship('ChecklistCompletion', back_populates='item', lazy='dynamic')
    
    def __repr__(self):
        return f'<ChecklistItem {self.name}>'


class ChecklistCompletion(db.Model):
    """Record of a staff member completing a checklist item."""
    __tablename__ = 'checklist_completions'
    
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('checklist_items.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    evidence_url = db.Column(db.String(500), nullable=True)  # Link to certificate/doc
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    staff = db.relationship('Staff', back_populates='checklist_completions')
    item = db.relationship('ChecklistItem', back_populates='completions')
    
    def __repr__(self):
        return f'<ChecklistCompletion {self.staff.full_name} - {self.item.name}>'


class GFSReconciliation(db.Model):
    """GFS invoice reconciliation record."""
    __tablename__ = 'gfs_reconciliations'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(100), nullable=False)
    invoice_date = db.Column(db.Date, nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected
    pdf_path = db.Column(db.String(500), nullable=True)
    csv_path = db.Column(db.String(500), nullable=True)
    reconciled_data = db.Column(db.JSON, nullable=True)  # Store reconciliation results
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.String(100), nullable=True)
    
    def __repr__(self):
        return f'<GFSReconciliation {self.invoice_number}>'
