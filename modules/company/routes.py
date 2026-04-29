from flask import request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from models.user import UserRole
from modules.company import company_bp
from schemas.company_settings_schema import CompanySettingsUpdateSchema
from services.company_settings_service import CompanySettingsService
from utils.responses import error, success
from utils.serialization import company_settings_dict

_service = CompanySettingsService()
_update = CompanySettingsUpdateSchema()


@company_bp.get("")
@jwt_required()
def get_company_settings():
    if current_user.role != UserRole.ADMIN.value:
        return error("Forbidden.", status_code=403)
    row = _service.get(current_user)
    return success(data={"company": company_settings_dict(row)})


@company_bp.put("")
@jwt_required()
def put_company_settings():
    if current_user.role != UserRole.ADMIN.value:
        return error("Forbidden.", status_code=403)
    try:
        data = _update.load(request.get_json() or {}, partial=True)
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    row, err = _service.update(current_user, data)
    if err:
        return error(err, status_code=403)
    return success("Company settings updated.", {"company": company_settings_dict(row)})
