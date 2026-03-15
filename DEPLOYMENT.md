# Deployment Notes - Kinawa CC v2

## VPS Deployment (2026-03-15)

### Infrastructure
- **Host**: p5gHxcyh7WDx.cloud.instance (162.212.153.134)
- **Path**: `/home/openclaw/kinawa-cc-v2/`
- **Port**: 5010 (was 5000, conflicted with aifoo)
- **Database**: PostgreSQL `kinawa_cc_v2`

### Environment
```bash
FLASK_ENV=production
DATABASE_URL=postgresql://kinawa:kinawa2026_secure@localhost/kinawa_cc_v2
ADMIN_USERNAME=admin
ADMIN_PASSWORD=kinawa2026
```

### Service
```bash
sudo systemctl status kinawa-cc-v2.service
sudo systemctl start|stop|restart kinawa-cc-v2.service
```

### Nginx
- Config: `/etc/nginx/sites-enabled/kinawa`
- Proxies to: `localhost:5010`
- SSL: Let's Encrypt for clubkinawa.net

### Database Setup
```bash
sudo -u postgres psql -c "CREATE DATABASE kinawa_cc_v2;"
sudo -u postgres psql -c "CREATE USER kinawa WITH PASSWORD 'kinawa2026_secure';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE kinawa_cc_v2 TO kinawa;"
sudo -u postgres psql -c "GRANT ALL ON SCHEMA public TO kinawa;"
sudo -u postgres psql -c "ALTER DATABASE kinawa_cc_v2 OWNER TO kinawa;"
```

### Initial Data
```bash
# Create tables and admin user
cd /home/openclaw/kinawa-cc-v2
source venv/bin/activate
python3 -c 'from run import app; from app.extensions import db; from app.models import User; 
with app.app_context():
    db.create_all()
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin", email="admin@clubkinawa.net")
        admin.set_password("kinawa2026")
        db.session.add(admin)
        db.session.commit()
        print("Admin created")
'
```
