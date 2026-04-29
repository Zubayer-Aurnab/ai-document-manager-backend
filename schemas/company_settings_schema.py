from marshmallow import Schema, fields, validate


class CompanySettingsUpdateSchema(Schema):
    company_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    legal_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    tagline = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    email = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    address_line1 = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    address_line2 = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    city = fields.Str(required=False, allow_none=True, validate=validate.Length(max=120))
    state_region = fields.Str(required=False, allow_none=True, validate=validate.Length(max=120))
    postal_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=40))
    country = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    website = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
