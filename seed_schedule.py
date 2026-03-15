#!/usr/bin/env python3
"""
Seed script for Kinawa CC v2 - Staff Schedule module.
Creates initial staff members and seeds typical shift assignments.
"""
import os
import sys

# Ensure we use the correct app module from this project
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Remove any conflicting paths that might have workspace/app.py
sys.path = [p for p in sys.path if not p.endswith('/workspace') or p == script_dir]

from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import Staff, ScheduleAssignment


# Staff data from MEMORY.md
STAFF_DATA = [
    {"name": "Adam", "before": [0, 1, 2, 3, 4], "after": [0, 1, 2, 3, 4]},  # Mon-Fri both
    {"name": "Ashlee", "before": [0, 3], "after": [1, 4]},  # Before: Mon, Thu; After: Tue, Fri
    {"name": "Kayden", "before": [1, 3, 4], "after": [0, 1, 3]},  # Before: Tue, Thu, Fri; After: Mon, Tue, Thu
    {"name": "Morgan", "before": [0, 2], "after": [0, 2, 3]},  # Before: Mon, Wed; After: Mon, Wed, Thu
    {"name": "Ethan", "before": [], "after": [0, 1, 3, 4]},  # After only: Mon, Tue, Thu, Fri
    {"name": "Khari", "before": [], "after": [0, 1]},  # After only: Mon, Tue
    {"name": "Gavin", "before": [], "after": [4]},  # After only: Fri
    {"name": "Avah", "before": [1], "after": []},  # Before only: Tue
    {"name": "Gibson", "before": [], "after": [2]},  # After only: Wed
]


def get_week_dates(date=None):
    """Get the Monday-Friday dates for the week containing the given date."""
    if date is None:
        date = datetime.now().date()
    # Find Monday of this week
    monday = date - timedelta(days=date.weekday())
    # Generate Mon-Fri dates
    return [monday + timedelta(days=i) for i in range(5)]


def seed_staff():
    """Create staff members."""
    print("Creating staff members...")
    staff_map = {}
    
    for staff_info in STAFF_DATA:
        # Check if staff already exists
        existing = Staff.query.filter_by(full_name=staff_info["name"]).first()
        if existing:
            print(f"  Staff '{staff_info['name']}' already exists (id={existing.id})")
            staff_map[staff_info["name"]] = existing
            continue
        
        staff = Staff(
            full_name=staff_info["name"],
            hire_date=None,  # Not specified
            active=True,
            notes=f"Typical shifts: Before {staff_info['before']}, After {staff_info['after']}"
        )
        db.session.add(staff)
        db.session.flush()  # Get the ID
        staff_map[staff_info["name"]] = staff
        print(f"  Created staff: {staff.full_name} (id={staff.id})")
    
    db.session.commit()
    return staff_map


def seed_schedule_assignments(staff_map):
    """Create schedule assignments for the current week and next week."""
    print("\nCreating schedule assignments...")
    
    # Get dates for current week and next week
    today = datetime.now().date()
    current_week = get_week_dates(today)
    next_week = get_week_dates(today + timedelta(weeks=1))
    
    weeks = [
        ("Current week", current_week),
        ("Next week", next_week)
    ]
    
    total_created = 0
    
    for week_name, week_dates in weeks:
        print(f"\n  {week_name}:")
        
        for staff_info in STAFF_DATA:
            staff = staff_map.get(staff_info["name"])
            if not staff:
                continue
            
            # Create before care assignments
            for day_idx in staff_info["before"]:
                date = week_dates[day_idx]
                
                # Check if assignment already exists
                existing = ScheduleAssignment.query.filter_by(
                    staff_id=staff.id,
                    date=date,
                    shift_type='before'
                ).first()
                
                if not existing:
                    assignment = ScheduleAssignment(
                        staff_id=staff.id,
                        date=date,
                        shift_type='before'
                    )
                    db.session.add(assignment)
                    total_created += 1
            
            # Create after care assignments
            for day_idx in staff_info["after"]:
                date = week_dates[day_idx]
                
                # Check if assignment already exists
                existing = ScheduleAssignment.query.filter_by(
                    staff_id=staff.id,
                    date=date,
                    shift_type='after'
                ).first()
                
                if not existing:
                    assignment = ScheduleAssignment(
                        staff_id=staff.id,
                        date=date,
                        shift_type='after'
                    )
                    db.session.add(assignment)
                    total_created += 1
            
            print(f"    - {staff.full_name}: Before {len(staff_info['before'])} days, After {len(staff_info['after'])} days")
    
    db.session.commit()
    print(f"\n  Total assignments created: {total_created}")


def main():
    """Main seed function."""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Kinawa CC v2 - Staff Schedule Seeding")
        print("=" * 60)
        
        # Create database tables if they don't exist
        db.create_all()
        
        # Seed staff
        staff_map = seed_staff()
        
        # Seed schedule assignments
        seed_schedule_assignments(staff_map)
        
        print("\n" + "=" * 60)
        print("Seeding complete!")
        print("=" * 60)
        
        # Print summary
        staff_count = Staff.query.count()
        assignment_count = ScheduleAssignment.query.count()
        print(f"\nDatabase summary:")
        print(f"  - Staff members: {staff_count}")
        print(f"  - Schedule assignments: {assignment_count}")


if __name__ == '__main__':
    main()
