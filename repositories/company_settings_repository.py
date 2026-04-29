"""Singleton company_settings row (id=1)."""
from typing import Optional

from extensions import db
from models.company_settings import CompanySettings

_DEFAULT_ID = 1


class CompanySettingsRepository:
    def get_singleton(self) -> Optional[CompanySettings]:
        return db.session.get(CompanySettings, _DEFAULT_ID)

    def get_or_create_empty(self) -> CompanySettings:
        row = self.get_singleton()
        if row:
            return row
        row = CompanySettings(id=_DEFAULT_ID)
        db.session.add(row)
        db.session.commit()
        return row

    def save(self, row: CompanySettings) -> CompanySettings:
        db.session.add(row)
        db.session.commit()
        return row
