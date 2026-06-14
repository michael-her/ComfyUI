from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SjsxMeta(BaseModel):
    domain: str | None = None
    layer: str | None = None
    status: str | None = None


class SjsxAgreement(BaseModel):
    agreed: list[str] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.agreed) + len(self.pending)

    @property
    def percent(self) -> int:
        if self.total == 0:
            return 100
        return round(len(self.agreed) / self.total * 100)


class SjsxDefinition(BaseModel):
    name: str
    body: str


class SjsxSection(BaseModel):
    comment: str | None = None
    definitions: list[SjsxDefinition] = Field(default_factory=list)


class SjsxNode(BaseModel):
    type: str
    name: str | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)
    children: list[str] = Field(default_factory=list)
    content: str | None = None


class SjsxGraph(BaseModel):
    document_type: Literal["sjsx"] = "sjsx"
    version: int = 1
    header: str = ""
    meta: SjsxMeta = Field(default_factory=SjsxMeta)
    agreement: SjsxAgreement = Field(default_factory=SjsxAgreement)
    sections: list[SjsxSection] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    nodes: dict[str, SjsxNode] = Field(default_factory=dict)
    bindings: dict[str, Any] = Field(default_factory=dict)
    comments: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SjsxGraph:
        return cls.model_validate(data)

    @classmethod
    def empty_template(cls, *, domain: str = "NewApp", layer: str = "ui") -> SjsxGraph:
        header = f'''/**
 * @sjsx
 * domain: {domain}
 * layer: {layer}
 * status: design
 *
 * Agreement items:
 * [ ] Initial layout
 */'''
        return cls(
            header=header,
            meta=SjsxMeta(domain=domain, layer=layer, status="design"),
            agreement=SjsxAgreement(pending=["Initial layout"]),
            sections=[],
            components=[],
        )
