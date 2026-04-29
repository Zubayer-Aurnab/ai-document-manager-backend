import re

from marshmallow import Schema, fields, validate


_SLUG_RE = re.compile(r"^[a-z0-9-]{0,40}$")


class DocumentUploadSchema(Schema):
    title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=8000))
    visibility = fields.Str(
        load_default="department",
        validate=validate.OneOf(["private", "department", "shared"]),
    )
    category_slug = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.And(validate.Length(max=40), validate.Regexp(_SLUG_RE)),
    )


class DocumentUpdateSchema(Schema):
    title = fields.Str(required=False, validate=validate.Length(min=1, max=300))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=8000))
    visibility = fields.Str(required=False, validate=validate.OneOf(["private", "department", "shared"]))
    category_slug = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.And(validate.Length(max=40), validate.Regexp(_SLUG_RE)),
    )
    tags = fields.List(
        fields.Str(validate=validate.Length(max=40)),
        required=False,
        allow_none=True,
        validate=validate.Length(max=25),
    )


class DocumentShareSchema(Schema):
    shared_with_user_id = fields.Int(load_default=None, allow_none=True)
    shared_with_department_id = fields.Int(load_default=None, allow_none=True)
    permission = fields.Str(
        required=True,
        validate=validate.OneOf(["view", "comment", "edit"]),
    )
    expires_at = fields.DateTime(required=False, allow_none=True)
