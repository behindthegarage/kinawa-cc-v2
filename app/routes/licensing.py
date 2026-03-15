from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_login import login_required
import os
import uuid
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Staff, ChecklistItem, ChecklistCompletion

bp = Blueprint('licensing', __name__, url_prefix='/licensing')

# Allowed file extensions for evidence uploads
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/')
@login_required
def dashboard():
    """Licensing dashboard - overview of all staff compliance status."""
    filter_type = request.args.get('filter', 'all')  # all, incomplete, category
    category_filter = request.args.get('category', '')
    
    # Get all active staff
    staff_list = Staff.query.filter_by(active=True).order_by(Staff.full_name).all()
    
    # Get all checklist items
    items = ChecklistItem.query.order_by(ChecklistItem.category, ChecklistItem.sort_order).all()
    
    # Build staff progress data
    staff_progress = []
    for staff in staff_list:
        completions = ChecklistCompletion.query.filter_by(staff_id=staff.id).all()
        completion_map = {c.item_id: c for c in completions}
        
        total_items = len(items)
        completed_count = 0
        expired_count = 0
        expiring_soon_count = 0
        incomplete_items = []
        
        for item in items:
            completion = completion_map.get(item.id)
            if completion:
                if completion.is_expired():
                    expired_count += 1
                    incomplete_items.append({'item': item, 'status': 'expired', 'completion': completion})
                elif completion.is_expiring_soon():
                    expiring_soon_count += 1
                    completed_count += 1
                else:
                    completed_count += 1
            else:
                incomplete_items.append({'item': item, 'status': 'incomplete', 'completion': None})
        
        # Filter logic
        if filter_type == 'incomplete' and completed_count == total_items:
            continue
        if category_filter:
            # Check if any incomplete items match the category
            if not any(ii['item'].category == category_filter for ii in incomplete_items):
                continue
        
        staff_progress.append({
            'staff': staff,
            'total': total_items,
            'completed': completed_count,
            'expired': expired_count,
            'expiring_soon': expiring_soon_count,
            'incomplete_items': incomplete_items,
            'percent_complete': int((completed_count / total_items * 100)) if total_items > 0 else 0
        })
    
    # Get unique categories for filter dropdown
    categories = db.session.query(ChecklistItem.category).distinct().order_by(ChecklistItem.category).all()
    categories = [c[0] for c in categories]
    
    return render_template(
        'licensing/dashboard.html',
        title='Licensing Dashboard',
        staff_progress=staff_progress,
        filter_type=filter_type,
        category_filter=category_filter,
        categories=categories,
        all_items=items
    )


@bp.route('/staff/<int:staff_id>')
@login_required
def staff_checklist(staff_id):
    """Individual staff compliance detail view."""
    staff = Staff.query.get_or_404(staff_id)
    
    # Get all checklist items
    items = ChecklistItem.query.order_by(ChecklistItem.category, ChecklistItem.sort_order).all()
    
    # Get completions for this staff
    completions = ChecklistCompletion.query.filter_by(staff_id=staff_id).all()
    completion_map = {c.item_id: c for c in completions}
    
    # Build checklist items with status
    checklist_data = []
    for item in items:
        completion = completion_map.get(item.id)
        checklist_data.append({
            'item': item,
            'completion': completion,
            'status': completion.status_class() if completion else 'incomplete'
        })
    
    return render_template(
        'licensing/staff_checklist.html',
        title=f'Licensing: {staff.full_name}',
        staff=staff,
        checklist_data=checklist_data
    )


@bp.route('/staff/<int:staff_id>/complete/<int:item_id>', methods=['GET', 'POST'])
@login_required
def complete_item(staff_id, item_id):
    """Mark a checklist item as complete with optional evidence upload."""
    staff = Staff.query.get_or_404(staff_id)
    item = ChecklistItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        completed_date_str = request.form.get('completed_date', '').strip()
        expires_date_str = request.form.get('expires_date', '').strip()
        notes = request.form.get('notes', '').strip()
        
        # Parse dates
        completed_date = datetime.utcnow()
        if completed_date_str:
            try:
                completed_date = datetime.strptime(completed_date_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid completed date format', 'error')
                return redirect(url_for('licensing.staff_checklist', staff_id=staff_id))
        
        expires_date = None
        if expires_date_str:
            try:
                expires_date = datetime.strptime(expires_date_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid expiration date format', 'error')
                return redirect(url_for('licensing.staff_checklist', staff_id=staff_id))
        
        # Check for existing completion
        completion = ChecklistCompletion.query.filter_by(
            staff_id=staff_id, item_id=item_id
        ).first()
        
        if completion:
            # Update existing
            completion.completed_at = completed_date
            completion.expires_at = expires_date
            completion.notes = notes
        else:
            # Create new
            completion = ChecklistCompletion(
                staff_id=staff_id,
                item_id=item_id,
                completed_at=completed_date,
                expires_at=expires_date,
                notes=notes
            )
            db.session.add(completion)
        
        # Handle file upload
        if 'evidence' in request.files:
            file = request.files['evidence']
            if file and file.filename and allowed_file(file.filename):
                # Check file size
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    flash('File size exceeds 5MB limit', 'error')
                    return redirect(url_for('licensing.staff_checklist', staff_id=staff_id))
                
                # Generate unique filename
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
                
                # Ensure upload directory exists
                upload_dir = os.path.join('instance', 'uploads', 'evidence')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Save file
                file_path = os.path.join(upload_dir, unique_filename)
                file.save(file_path)
                
                # Store relative path
                completion.evidence_url = f"uploads/evidence/{unique_filename}"
        
        db.session.commit()
        flash(f'{item.name} marked as complete', 'success')
        return redirect(url_for('licensing.staff_checklist', staff_id=staff_id))
    
    return render_template(
        'licensing/complete_form.html',
        title=f'Complete: {item.name}',
        staff=staff,
        item=item
    )


@bp.route('/staff/<int:staff_id>/uncomplete/<int:item_id>', methods=['POST'])
@login_required
def uncomplete_item(staff_id, item_id):
    """Mark a checklist item as incomplete (delete completion record)."""
    staff = Staff.query.get_or_404(staff_id)
    item = ChecklistItem.query.get_or_404(item_id)
    
    completion = ChecklistCompletion.query.filter_by(
        staff_id=staff_id, item_id=item_id
    ).first()
    
    if completion:
        # Delete associated file if exists
        if completion.evidence_url:
            file_path = os.path.join('instance', completion.evidence_url)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.delete(completion)
        db.session.commit()
        flash(f'{item.name} marked as incomplete', 'success')
    
    return redirect(url_for('licensing.staff_checklist', staff_id=staff_id))


@bp.route('/evidence/<path:filename>')
@login_required
def view_evidence(filename):
    """Serve evidence files."""
    return send_from_directory(
        os.path.join('instance', 'uploads', 'evidence'),
        filename,
        as_attachment=False
    )


@bp.route('/evidence/<path:filename>/download')
@login_required
def download_evidence(filename):
    """Download evidence files."""
    return send_from_directory(
        os.path.join('instance', 'uploads', 'evidence'),
        filename,
        as_attachment=True,
        download_name=filename
    )


# ==================== CHECKLIST ITEM MANAGEMENT ====================

@bp.route('/items/')
@login_required
def items_list():
    """Admin view: List all checklist items."""
    items = ChecklistItem.query.order_by(ChecklistItem.category, ChecklistItem.sort_order).all()
    return render_template(
        'licensing/items.html',
        title='Licensing Checklist Items',
        items=items
    )


@bp.route('/items/add', methods=['GET', 'POST'])
@login_required
def add_item():
    """Add a new checklist item."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        required_for = request.form.get('required_for', 'all')
        sort_order = request.form.get('sort_order', '0')
        
        if not name:
            flash('Name is required', 'error')
            return render_template('licensing/item_form.html', title='Add Checklist Item')
        
        if not category:
            flash('Category is required', 'error')
            return render_template('licensing/item_form.html', title='Add Checklist Item')
        
        try:
            sort_order = int(sort_order)
        except ValueError:
            sort_order = 0
        
        item = ChecklistItem(
            name=name,
            description=description,
            category=category,
            required_for=required_for,
            sort_order=sort_order
        )
        db.session.add(item)
        db.session.commit()
        
        flash(f'Checklist item "{name}" added successfully', 'success')
        return redirect(url_for('licensing.items_list'))
    
    return render_template('licensing/item_form.html', title='Add Checklist Item', item=None)


@bp.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    """Edit a checklist item."""
    item = ChecklistItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        required_for = request.form.get('required_for', 'all')
        sort_order = request.form.get('sort_order', '0')
        
        if not name:
            flash('Name is required', 'error')
            return render_template('licensing/item_form.html', title='Edit Checklist Item', item=item)
        
        if not category:
            flash('Category is required', 'error')
            return render_template('licensing/item_form.html', title='Edit Checklist Item', item=item)
        
        try:
            sort_order = int(sort_order)
        except ValueError:
            sort_order = 0
        
        item.name = name
        item.description = description
        item.category = category
        item.required_for = required_for
        item.sort_order = sort_order
        
        db.session.commit()
        
        flash(f'Checklist item "{name}" updated successfully', 'success')
        return redirect(url_for('licensing.items_list'))
    
    return render_template('licensing/item_form.html', title='Edit Checklist Item', item=item)


@bp.route('/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    """Delete a checklist item and all associated completions."""
    item = ChecklistItem.query.get_or_404(item_id)
    
    # Delete associated completions and their evidence files
    completions = ChecklistCompletion.query.filter_by(item_id=item_id).all()
    for completion in completions:
        if completion.evidence_url:
            file_path = os.path.join('instance', completion.evidence_url)
            if os.path.exists(file_path):
                os.remove(file_path)
        db.session.delete(completion)
    
    db.session.delete(item)
    db.session.commit()
    
    flash(f'Checklist item "{item.name}" deleted successfully', 'success')
    return redirect(url_for('licensing.items_list'))


@bp.route('/seed', methods=['POST'])
@login_required
def seed_checklist_items():
    """Seed pre-defined Michigan child care licensing checklist items."""
    seed_items = [
        {
            'name': 'CPR Certification',
            'description': 'Current CPR certification for infants and children',
            'category': 'Training',
            'required_for': 'all',
            'sort_order': 1
        },
        {
            'name': 'First Aid Certification',
            'description': 'Current First Aid certification',
            'category': 'Training',
            'required_for': 'all',
            'sort_order': 2
        },
        {
            'name': 'Bloodborne Pathogen Training',
            'description': 'Annual training on bloodborne pathogen safety',
            'category': 'Training',
            'required_for': 'all',
            'sort_order': 3
        },
        {
            'name': 'TB Test',
            'description': 'TB test results (valid for 2 years)',
            'category': 'Health',
            'required_for': 'all',
            'sort_order': 4
        },
        {
            'name': 'Background Check',
            'description': 'Completed criminal background check and fingerprinting',
            'category': 'Background',
            'required_for': 'all',
            'sort_order': 5
        },
        {
            'name': 'Abuse & Neglect Training',
            'description': 'Training on recognizing and reporting child abuse and neglect',
            'category': 'Training',
            'required_for': 'all',
            'sort_order': 6
        },
        {
            'name': 'Sudden Infant Death Syndrome (SIDS) Training',
            'description': 'Training on SIDS prevention and safe sleep practices',
            'category': 'Training',
            'required_for': 'all',
            'sort_order': 7
        }
    ]
    
    added_count = 0
    for item_data in seed_items:
        # Check if item already exists
        existing = ChecklistItem.query.filter_by(name=item_data['name']).first()
        if not existing:
            item = ChecklistItem(**item_data)
            db.session.add(item)
            added_count += 1
    
    db.session.commit()
    
    if added_count > 0:
        flash(f'{added_count} checklist items added successfully', 'success')
    else:
        flash('All checklist items already exist', 'info')
    
    return redirect(url_for('licensing.items_list'))
