import re

from marshmallow import Schema, ValidationError, fields, validate, validates_schema


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


class DocumentShareUpdateSchema(Schema):
    """PATCH body: change permission and/or expiry (``expires_at: null`` clears expiry)."""

    permission = fields.Str(required=False, validate=validate.OneOf(["view", "comment", "edit"]))
    expires_at = fields.DateTime(required=False, allow_none=True)

    @validates_schema
    def require_at_least_one_field(self, data, **kwargs):
        if not data:
            raise ValidationError("Submit at least one of: permission, expires_at.")
