from marshmallow import Schema, fields, validate


class DocumentCategoryCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    slug = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=40),
    )


class DocumentCategoryUpdateSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=1, max=120))
