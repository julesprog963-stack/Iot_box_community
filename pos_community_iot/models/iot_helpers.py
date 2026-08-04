from __future__ import annotations


def _safe_text(value):
    return str(value or "").strip()


def _truncate(text, max_length):
    raw = _safe_text(text)
    if len(raw) <= max_length:
        return raw
    if max_length <= 3:
        return raw[:max_length]
    return f"{raw[: max_length - 3]}..."


def _width_for_device(device):
    if hasattr(device, "_get_ticket_text_width"):
        return device._get_ticket_text_width()
    if getattr(device, "type", None) == "standard_printer" or getattr(device, "ticket_mode", None) == "standard":
        return 80
    if getattr(device, "ticket_mode", None) == "wide":
        return 56
    return 42


def _center(text, width):
    return _truncate(text, width).center(width)


def _label_value(label, value, width):
    prefix = f"{label}: "
    return f"{prefix}{_truncate(value, max(5, width - len(prefix)))}"


def _line_with_amount(label, amount_text, width):
    left = _truncate(label, max(1, width - len(amount_text) - 1))
    space_count = max(1, width - len(left) - len(amount_text))
    return f"{left}{' ' * space_count}{amount_text}"


def _format_money(amount):
    try:
        return f"{float(amount):,.2f}"
    except (TypeError, ValueError):
        return _safe_text(amount) or "0.00"


def _item_line(qty, description, amount_text, width):
    left = f"{qty} x {description}" if qty else description
    return _line_with_amount(left, amount_text, width)


def _append_if_value(lines, value, width, centered=False):
    text = _safe_text(value)
    if not text:
        return
    if centered:
        lines.append(_center(text, width))
    else:
        lines.append(_truncate(text, width))


def build_receipt_lines(pos_config, device, receipt_data, order_ref=None):
    width = _width_for_device(device)
    separator = "-" * width
    strong = "=" * width
    header_data = receipt_data.get("headerData") or {}
    company = header_data.get("company") or {}
    company_name = _safe_text(company.get("name") or pos_config.company_id.name or "EMPRESA").upper()
    order_name = _safe_text(order_ref or receipt_data.get("name") or "-")
    date_value = _safe_text(receipt_data.get("date") or "-")
    cashier = _safe_text(receipt_data.get("cashier") or header_data.get("cashier") or "-")
    company_partner = company.get("partner_id") or []
    company_contact = company_partner[1] if len(company_partner) > 1 else ""
    company_phone = _safe_text(company.get("phone"))
    company_vat = _safe_text(company.get("vat"))
    company_email = _safe_text(company.get("email"))
    company_website = _safe_text(company.get("website"))
    receipt_header = _safe_text(header_data.get("header") or pos_config.receipt_header or "")
    footer = _safe_text(receipt_data.get("footer") or pos_config.receipt_footer or "")
    tracking_number = _safe_text(header_data.get("trackingNumber"))
    shipping_date = _safe_text(receipt_data.get("shippingDate"))
    ticket_code = _safe_text(receipt_data.get("ticket_code"))

    lines = [
        strong,
        _center(company_name, width),
        _center("TICKET POS", width),
        strong,
    ]

    _append_if_value(lines, company_contact, width, centered=True)
    if company_phone:
        lines.append(_label_value("Tel", company_phone, width))
    if company_vat:
        lines.append(_label_value("RFC", company_vat, width))
    _append_if_value(lines, company_email, width, centered=True)
    _append_if_value(lines, company_website, width, centered=True)
    if receipt_header:
        lines.append(separator)
        for header_line in receipt_header.splitlines():
            _append_if_value(lines, header_line, width, centered=True)
    if cashier and cashier != "-":
        lines.append(separator)
        lines.append(_center(f"Atendido por {cashier}", width))
    if tracking_number:
        lines.append(_center(f"Turno {tracking_number}", width))

    lines.extend(
        [
            separator,
            _label_value("Orden", order_name, width),
            _label_value("Fecha", date_value, width),
            separator,
        ]
    )

    for line in receipt_data.get("orderlines", []):
        qty = _safe_text(line.get("qty") or "1")
        name = _safe_text(line.get("productName") or "Producto")
        amount = _safe_text(line.get("price")) or _format_money(0)
        lines.append(_item_line(qty, name, amount, width))
        note = _safe_text(line.get("customerNote"))
        if note:
            lines.append(f"  Nota: {_truncate(note, max(1, width - 8))}")

    lines.extend(
        [
            separator,
            _line_with_amount("Subtotal", _format_money(receipt_data.get("total_without_tax")), width),
            _line_with_amount("Impuestos", _format_money(receipt_data.get("amount_tax")), width),
            _line_with_amount("Total", _format_money(receipt_data.get("amount_total")), width),
        ]
    )

    change_amount = receipt_data.get("change")
    if change_amount:
        lines.append(_line_with_amount("Cambio", _format_money(change_amount), width))

    if receipt_data.get("paymentlines"):
        lines.append(separator)
        lines.append(_center("PAGOS", width))
        for payment in receipt_data.get("paymentlines", []):
            lines.append(
                _line_with_amount(
                    _safe_text(payment.get("name") or "Pago"),
                    _format_money(payment.get("amount")),
                    width,
                )
            )

    tax_details = receipt_data.get("tax_details") or []
    if tax_details:
        lines.append(separator)
        lines.append(_center("IMPUESTOS", width))
        for tax_line in tax_details:
            tax = tax_line.get("tax") or {}
            tax_name = _safe_text(tax.get("name") or tax.get("amount") or "Tax")
            lines.append(
                _line_with_amount(
                    tax_name,
                    _format_money(tax_line.get("amount")),
                    width,
                )
            )

    total_discount = receipt_data.get("total_discount")
    if total_discount:
        lines.append(separator)
        lines.append(_line_with_amount("Descuentos", _format_money(total_discount), width))

    if shipping_date:
        lines.append(separator)
        lines.append(_label_value("Entrega esperada", shipping_date, width))

    if ticket_code:
        lines.append(separator)
        lines.append(_center("CODIGO DE FACTURA", width))
        lines.append(_center(ticket_code, width))

    if footer:
        lines.append(separator)
        for footer_line in footer.splitlines():
            _append_if_value(lines, footer_line, width, centered=True)

    lines.extend(
        [
            separator,
            _center("Powered by Odoo", width),
            _center(order_name, width),
            _center(date_value, width),
        ]
    )
    lines.append(strong)
    return lines



def build_folio_lines(pos_config, device, folio_data):
    width = _width_for_device(device)
    company_name = _safe_text(folio_data.get("companyName") or pos_config.company_id.name or "EMPRESA").upper()
    order_name = _safe_text(folio_data.get("orderName") or "-")
    date_value = _safe_text(folio_data.get("date") or "-")
    total = _format_money(folio_data.get("total"))

    return [
        _center(company_name, width),
        _center("FOLIO", width),
        _center(order_name, width),
        _label_value("Fecha", date_value, width),
        _label_value("Total", total, width),
    ]



def build_preparation_lines(printer, device, payload):
    width = _width_for_device(device)
    separator = "-" * width
    strong = "=" * width
    changes = payload.get("printing_changes") or {}
    order_name = _safe_text(payload.get("order_ref") or changes.get("name") or "ORDEN")
    table_name = _safe_text(changes.get("table_name") or "")
    floor_name = _safe_text(changes.get("floor_name") or "")
    time_data = changes.get("time") or {}
    time_label = f"{_safe_text(time_data.get('hours'))}:{_safe_text(time_data.get('minutes'))}".strip(":") or "-"

    lines = [
        strong,
        _center((printer.name or "IMPRESORA PREPARACION").upper(), width),
        _center("COMANDA", width),
        strong,
        _label_value("Orden", order_name, width),
        _label_value("Hora", time_label, width),
    ]

    if table_name:
        lines.append(_label_value("Mesa", table_name, width))
    if floor_name:
        lines.append(_label_value("Area", floor_name, width))

    lines.append(separator)

    new_lines = changes.get("new") or []
    cancelled_lines = changes.get("cancelled") or []

    if new_lines:
        lines.append(_center("NUEVOS", width))
        for line in new_lines:
            lines.append(_item_line(line.get("quantity"), line.get("name"), "", width).rstrip())
            note = _safe_text(line.get("note"))
            if note:
                lines.append(f"  Nota: {_truncate(note, max(1, width - 8))}")
        lines.append(separator)

    if cancelled_lines:
        lines.append(_center("CANCELADOS", width))
        for line in cancelled_lines:
            lines.append(_item_line(line.get("quantity"), line.get("name"), "", width).rstrip())
            note = _safe_text(line.get("note"))
            if note:
                lines.append(f"  Nota: {_truncate(note, max(1, width - 8))}")
        lines.append(separator)

    lines.append(strong)
    return lines
