from marshmallow import Schema, fields, validate


class UserCreateSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    full_name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    role = fields.Str(load_default="user", validate=validate.OneOf(["admin", "user"]))
    department_id = fields.Int(load_default=None, allow_none=True)


class UserUpdateSchema(Schema):
    full_name = fields.Str(required=False)
    password = fields.Str(required=False, validate=validate.Length(min=8))
    role = fields.Str(required=False, validate=validate.OneOf(["admin", "user"]))
    department_id = fields.Int(required=False, allow_none=True)
    is_active = fields.Bool(required=False)
