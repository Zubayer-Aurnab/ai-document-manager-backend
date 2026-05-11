from marshmallow import Schema, fields, validate


class WorkspaceAskSchema(Schema):
    message = fields.Str(required=True, validate=validate.Length(min=2, max=4000))
