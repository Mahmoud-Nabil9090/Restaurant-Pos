# Copyright (c) 2026, mahmoud and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

ACTIVE_STATUSES = ("Open", "Sent to Kitchen", "Served")


class RestaurantOrder(Document):
    def validate(self):
        self.validate_table()
        self.calculate_totals()

    def validate_table(self):
        if self.order_type != "Dine In":
            return
        if not self.table:
            frappe.throw(_("Table is required for Dine In orders"))

        clash = frappe.db.exists(
            "Restaurant Order",
            {
                "table": self.table,
                "status": ["in", ACTIVE_STATUSES],
                "name": ["!=", self.name],
            },
        )
        if clash and self.status in ACTIVE_STATUSES:
            frappe.throw(
                _("Table {0} already has an open order: {1}").format(self.table, clash)
            )

    def calculate_totals(self):
        total_qty = net_total = 0
        for row in self.items:
            row.amount = flt(row.qty) * flt(row.rate)
            total_qty += flt(row.qty)
            net_total += row.amount

        self.total_qty = total_qty
        self.net_total = net_total
        self.grand_total = max(net_total - flt(self.discount_amount), 0)

    def on_update(self):
        self.sync_table_status()

    def sync_table_status(self):
        if self.order_type != "Dine In" or not self.table:
            return
        active = self.status in ACTIVE_STATUSES
        frappe.db.set_value(
            "Restaurant Table",
            self.table,
            {
                "status": "Occupied" if active else "Available",
                "current_order": self.name if active else None,
            },
        )