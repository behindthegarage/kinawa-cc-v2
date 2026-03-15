from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.extensions import db
from app.models import Staff, ScheduleAssignment

bp = Blueprint('staff', __name__, url_prefix='/staff')


@bp.route('/')
@login_required
def index():
    """List all staff members."""
    show_inactive = request.args.get('show_inactive', '0') == '1'
    
    query = Staff.query
    if not show_inactive:
        query = query.filter_by(active=True)
    
    staff_list = query.order_by(Staff.full_name).all()
    
    return render_template(
        'staff/index.html',
        title='Staff Management',
        staff_list=staff_list,
        show_inactive=show_inactive
    )


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new staff member."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        hire_date_str = request.form.get('hire_date', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not full_name:
            flash('Full name is required', 'error')
            return render_template('staff/form.html', title='Add Staff Member')
        
        # Parse hire date if provided
        hire_date = None
        if hire_date_str:
            try:
                hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid hire date format', 'error')
                return render_template('staff/form.html', title='Add Staff Member')
        
        staff = Staff(
            full_name=full_name,
            hire_date=hire_date,
            notes=notes,
            active=True
        )
        db.session.add(staff)
        db.session.commit()
        
        flash(f'Staff member "{full_name}" added successfully', 'success')
        return redirect(url_for('staff.index'))
    
    return render_template('staff/form.html', title='Add Staff Member', staff=None)


@bp.route('/<int:staff_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(staff_id):
    """Edit a staff member."""
    staff = Staff.query.get_or_404(staff_id)
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        hire_date_str = request.form.get('hire_date', '').strip()
        notes = request.form.get('notes', '').strip()
        active = request.form.get('active') == 'on'
        
        if not full_name:
            flash('Full name is required', 'error')
            return render_template('staff/form.html', title='Edit Staff Member', staff=staff)
        
        # Parse hire date if provided
        hire_date = None
        if hire_date_str:
            try:
                hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid hire date format', 'error')
                return render_template('staff/form.html', title='Edit Staff Member', staff=staff)
        
        staff.full_name = full_name
        staff.hire_date = hire_date
        staff.notes = notes
        staff.active = active
        staff.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Staff member "{full_name}" updated successfully', 'success')
        return redirect(url_for('staff.index'))
    
    return render_template('staff/form.html', title='Edit Staff Member', staff=staff)


@bp.route('/<int:staff_id>/toggle-active', methods=['POST'])
@login_required
def toggle_active(staff_id):
    """Toggle staff member active status (deactivate/activate)."""
    staff = Staff.query.get_or_404(staff_id)
    
    staff.active = not staff.active
    staff.updated_at = datetime.utcnow()
    db.session.commit()
    
    status = 'activated' if staff.active else 'deactivated'
    flash(f'Staff member "{staff.full_name}" {status}', 'success')
    return redirect(url_for('staff.index'))


@bp.route('/<int:staff_id>')
@login_required
def detail(staff_id):
    """View staff member details and schedule history."""
    staff = Staff.query.get_or_404(staff_id)
    
    # Get recent schedule assignments (last 30 days and next 30 days)
    today = datetime.now().date()
    from datetime import timedelta
    
    recent_assignments = ScheduleAssignment.query.filter(
        ScheduleAssignment.staff_id == staff_id,
        ScheduleAssignment.date >= today - timedelta(days=30),
        ScheduleAssignment.date <= today + timedelta(days=30)
    ).order_by(ScheduleAssignment.date).all()
    
    return render_template(
        'staff/detail.html',
        title=f'Staff: {staff.full_name}',
        staff=staff,
        assignments=recent_assignments
    )
