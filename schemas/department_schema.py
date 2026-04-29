from marshmallow import Schema, fields, validate


class DepartmentCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))


class DepartmentUpdateSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=1, max=120))
    description = fields.Str(required=False, allow_none=True)
