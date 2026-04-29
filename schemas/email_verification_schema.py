from marshmallow import Schema, fields


class VerifyEmailSchema(Schema):
    token = fields.Str(required=True)
