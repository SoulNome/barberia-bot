from app.extensions import db
from datetime import datetime


class ContactMap(db.Model):
    """Mapeo de @lid → número de teléfono real."""
    __tablename__ = "contact_map"

    id         = db.Column(db.Integer, primary_key=True)
    lid        = db.Column(db.String(64), unique=True, nullable=False, index=True)
    phone      = db.Column(db.String(32), nullable=False)
    push_name  = db.Column(db.String(128))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ContactMap {self.lid} → {self.phone}>"
