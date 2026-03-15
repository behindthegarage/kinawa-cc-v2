from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.extensions import db
from app.models import Staff, ScheduleAssignment

bp = Blueprint('schedule', __name__, url_prefix='/schedule')


def get_week_dates(date=None):
    """Get the Monday-Friday dates for the week containing the given date."""
    if date is None:
        date = datetime.now().date()
    
    # Find Monday of this week
    monday = date - timedelta(days=date.weekday())
    
    # Generate Mon-Fri dates
    week_dates = []
    for i in range(5):  # Monday = 0, Friday = 4
        week_dates.append(monday + timedelta(days=i))
    
    return week_dates


def get_week_boundaries(date=None):
    """Get the start (Monday) and end (Friday) of the week."""
    week_dates = get_week_dates(date)
    return week_dates[0], week_dates[-1]


@bp.route('/')
@login_required
def index():
    """Weekly schedule view."""
    # Get week offset from query param
    week_offset = request.args.get('week', 0, type=int)
    
    # Calculate the target date based on offset
    base_date = datetime.now().date()
    target_date = base_date + timedelta(weeks=week_offset)
    
    # Get Mon-Fri dates for this week
    week_dates = get_week_dates(target_date)
    monday, friday = week_dates[0], week_dates[-1]
    
    # Fetch all active staff
    staff_list = Staff.query.filter_by(active=True).order_by(Staff.full_name).all()
    
    # Fetch schedule assignments for this week
    assignments = ScheduleAssignment.query.filter(
        ScheduleAssignment.date >= monday,
        ScheduleAssignment.date <= friday
    ).all()
    
    # Build schedule grid: {date: {shift_type: [staff_names]}}
    schedule_grid = {}
    for date in week_dates:
        schedule_grid[date] = {
            'before': [],
            'after': []
        }
    
    for assignment in assignments:
        if assignment.date in schedule_grid:
            staff_name = assignment.staff.full_name if assignment.staff else 'Unknown'
            schedule_grid[assignment.date][assignment.shift_type].append({
                'id': assignment.id,
                'staff_id': assignment.staff_id,
                'staff_name': staff_name
            })
    
    return render_template(
        'schedule/index.html',
        title='Staff Schedule',
        week_dates=week_dates,
        monday=monday,
        friday=friday,
        week_offset=week_offset,
        prev_week=week_offset - 1,
        next_week=week_offset + 1,
        staff_list=staff_list,
        schedule_grid=schedule_grid,
        today=base_date
    )


@bp.route('/assign', methods=['GET', 'POST'])
@bp.route('/assign/<int:assignment_id>/edit', methods=['GET', 'POST'])
@login_required
def assign(assignment_id=None):
    """Assign staff to a shift (modal/form endpoint)."""
    
    if request.method == 'POST':
        staff_id = request.form.get('staff_id', type=int)
        date_str = request.form.get('date')
        shift_type = request.form.get('shift_type')
        
        if not all([staff_id, date_str, shift_type]):
            if request.headers.get('HX-Request'):
                return '<span class="error">Missing required fields</span>', 400
            flash('Missing required fields', 'error')
            return redirect(url_for('schedule.index'))
        
        # Parse date
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            if request.headers.get('HX-Request'):
                return '<span class="error">Invalid date format</span>', 400
            flash('Invalid date format', 'error')
            return redirect(url_for('schedule.index'))
        
        # Check for double-booking (same staff, same day, opposite shift)
        opposite_shift = 'after' if shift_type == 'before' else 'before'
        existing_opposite = ScheduleAssignment.query.filter_by(
            staff_id=staff_id,
            date=date,
            shift_type=opposite_shift
        ).first()
        
        if existing_opposite:
            msg = f'Staff already assigned to {opposite_shift} care on this date'
            if request.headers.get('HX-Request'):
                return f'<span class="error">{msg}</span>', 400
            flash(msg, 'error')
            return redirect(url_for('schedule.index'))
        
        # Check if editing existing assignment
        if assignment_id:
            assignment = ScheduleAssignment.query.get_or_404(assignment_id)
            assignment.staff_id = staff_id
            assignment.date = date
            assignment.shift_type = shift_type
        else:
            # Check if assignment already exists for this slot
            existing = ScheduleAssignment.query.filter_by(
                staff_id=staff_id,
                date=date,
                shift_type=shift_type
            ).first()
            
            if existing:
                msg = 'Staff already assigned to this shift'
                if request.headers.get('HX-Request'):
                    return f'<span class="error">{msg}</span>', 400
                flash(msg, 'error')
                return redirect(url_for('schedule.index'))
            
            assignment = ScheduleAssignment(
                staff_id=staff_id,
                date=date,
                shift_type=shift_type
            )
            db.session.add(assignment)
        
        db.session.commit()
        
        if request.headers.get('HX-Request'):
            slot_assignments = ScheduleAssignment.query.filter_by(
                date=date,
                shift_type=shift_type
            ).order_by(ScheduleAssignment.id).all()

            assignments_data = [
                {
                    'id': item.id,
                    'staff_name': item.staff.full_name if item.staff else 'Unknown'
                }
                for item in slot_assignments
            ]

            return render_template(
                'schedule/_assignment_cell.html',
                assignments=assignments_data,
                date=date_str,
                shift_type=shift_type
            )
        
        flash('Assignment saved successfully', 'success')
        return redirect(url_for('schedule.index'))
    
    # GET request - show form
    date_str = request.args.get('date')
    shift_type = request.args.get('shift_type')
    
    assignment = None
    if assignment_id:
        assignment = ScheduleAssignment.query.get_or_404(assignment_id)
        date_str = assignment.date.strftime('%Y-%m-%d')
        shift_type = assignment.shift_type
    
    active_staff = Staff.query.filter_by(active=True).order_by(Staff.full_name).all()
    
    return render_template(
        'schedule/assign_form.html',
        assignment=assignment,
        date_str=date_str,
        shift_type=shift_type,
        staff_list=active_staff
    )


@bp.route('/assign/<int:assignment_id>/delete', methods=['POST', 'DELETE'])
@login_required
def delete_assignment(assignment_id):
    """Delete a schedule assignment."""
    assignment = ScheduleAssignment.query.get_or_404(assignment_id)
    
    db.session.delete(assignment)
    db.session.commit()
    
    if request.headers.get('HX-Request'):
        date_str = request.form.get('date') or request.args.get('date') or assignment.date.strftime('%Y-%m-%d')
        shift_type = request.form.get('shift_type') or request.args.get('shift_type') or assignment.shift_type

        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        remaining_assignments = ScheduleAssignment.query.filter_by(
            date=date,
            shift_type=shift_type
        ).order_by(ScheduleAssignment.id).all()

        assignments_data = [
            {
                'id': item.id,
                'staff_name': item.staff.full_name if item.staff else 'Unknown'
            }
            for item in remaining_assignments
        ]

        return render_template(
            'schedule/_assignment_cell.html',
            assignments=assignments_data,
            date=date_str,
            shift_type=shift_type
        )
    
    flash('Assignment removed', 'success')
    return redirect(url_for('schedule.index'))


@bp.route('/cell')
@login_required
def cell_content():
    """Get cell content for HTMX updates."""
    date_str = request.args.get('date')
    shift_type = request.args.get('shift_type')
    
    if not date_str or not shift_type:
        return '', 400
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return '', 400
    
    assignments = ScheduleAssignment.query.filter_by(
        date=date,
        shift_type=shift_type
    ).all()
    
    if assignments:
        staff_names = [a.staff.full_name for a in assignments if a.staff]
        return ', '.join(staff_names) if staff_names else 'Unassigned'
    
    return '<span class="unassigned">+ Add</span>'


@bp.route('/print')
@login_required
def print_view():
    """Print-friendly schedule view."""
    # Get week offset from query param
    week_offset = request.args.get('week', 0, type=int)
    
    # Calculate the target date based on offset
    base_date = datetime.now().date()
    target_date = base_date + timedelta(weeks=week_offset)
    
    # Get Mon-Fri dates for this week
    week_dates = get_week_dates(target_date)
    monday, friday = week_dates[0], week_dates[-1]
    
    # Fetch all active staff
    staff_list = Staff.query.filter_by(active=True).order_by(Staff.full_name).all()
    
    # Fetch schedule assignments for this week
    assignments = ScheduleAssignment.query.filter(
        ScheduleAssignment.date >= monday,
        ScheduleAssignment.date <= friday
    ).all()
    
    # Build schedule grid: {date: {shift_type: [staff_names]}}
    schedule_grid = {}
    for date in week_dates:
        schedule_grid[date] = {
            'before': [],
            'after': []
        }
    
    for assignment in assignments:
        if assignment.date in schedule_grid:
            staff_name = assignment.staff.full_name if assignment.staff else 'Unknown'
            schedule_grid[assignment.date][assignment.shift_type].append(staff_name)
    
    return render_template(
        'schedule/print.html',
        title='Staff Schedule - Print View',
        week_dates=week_dates,
        monday=monday,
        friday=friday,
        week_offset=week_offset,
        schedule_grid=schedule_grid
    )
