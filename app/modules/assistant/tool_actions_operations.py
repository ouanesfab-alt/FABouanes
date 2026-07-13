# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict
from app.modules.assistant.tool_actions import sanitize_numeric, EXPENSE_CATEGORY_MAP, _ALLOWED_EXPENSE_CATEGORIES

logger = logging.getLogger("fabouanes.assistant")

async def handle_operations(func_name: str, func_args: dict, session_maker, user_role: str = 'operator') -> Dict[str, Any] | None:

    if func_name == "add_sale":
            client_id = func_args.get("client_id")
            if client_id:
                client_id = int(client_id)
            item_kind = str(func_args.get("item_kind", "finished")).strip().lower()
            item_id = func_args.get("item_id") or func_args.get("finished_product_id")
            if item_id is None:
                return {"error": "Paramètre finished_product_id ou item_id requis."}
            item_id = int(item_id)
            quantity = sanitize_numeric(func_args.get("quantity"))
            unit = str(func_args.get("unit", "kg")).strip().lower()
            unit_price = sanitize_numeric(func_args.get("unit_price"))
            amount_paid = sanitize_numeric(func_args.get("amount_paid", 0.0))
            notes = str(func_args.get("notes", "")).strip()
            from app.modules.sales.service import SalesService
            from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema
            line = SaleLineSchema(item_key=f"{item_kind}:{item_id}", quantity=quantity, unit=unit, unit_price=unit_price)
            schema = SaleFormSchema(client_id=client_id, notes=notes, lines=[line])
            async with session_maker() as session:
                service = SalesService(session)
                res = await service.create_sale_from_form(schema)
                if amount_paid > 0 and client_id:
                    from app.modules.payments.service import PaymentsService
                    from app.modules.payments.schemas_validation import PaymentFormSchema
                    pay_service = PaymentsService(session)
                    pay_schema = PaymentFormSchema(client_id=client_id, amount=amount_paid, payment_type="versement", notes=f"Paiement partiel vente {res.get('sale_id') or res.get('document_id')}")
                    await pay_service.create_payment_from_form(pay_schema)
                await session.commit()
            return {"success": True, "sale_id": res.get("sale_id") or res.get("document_id") or res.get("print_item_id")}

    elif func_name == "add_purchase":
            supplier_id = func_args.get("supplier_id")
            if supplier_id:
                supplier_id = int(supplier_id)
            item_kind = str(func_args.get("item_kind", "raw")).strip().lower()
            item_id = func_args.get("item_id") or func_args.get("raw_material_id")
            if item_id is None:
                return {"error": "Paramètre raw_material_id ou item_id requis."}
            item_id = int(item_id)
            quantity = sanitize_numeric(func_args.get("quantity"))
            unit = str(func_args.get("unit", "kg")).strip().lower()
            unit_price = sanitize_numeric(func_args.get("unit_price"))
            notes = str(func_args.get("notes", "")).strip()
            from app.modules.purchases.service import PurchaseService
            from app.modules.purchases.schemas_validation import PurchaseFormSchema, PurchaseLineSchema
            line = PurchaseLineSchema(raw_material_id=f"{item_kind}:{item_id}", quantity=quantity, unit=unit, unit_price=unit_price)
            schema = PurchaseFormSchema(supplier_id=supplier_id, notes=notes, lines=[line])
            async with session_maker() as session:
                service = PurchaseService(session)
                res = await service.create_purchase_from_form(schema)
                await session.commit()
            return {"success": True, "purchase_id": res.get("purchase_id") or res.get("document_id")}

    elif func_name == "add_payment":
            client_id = int(func_args.get("client_id"))
            amount = sanitize_numeric(func_args.get("amount"))
            payment_type = str(func_args.get("payment_type", "versement")).strip().lower()
            # Ensure it is exactly one of the accepted payments enums: versement or avance
            if payment_type not in ("versement", "avance"):
                payment_type = "versement"
            notes = str(func_args.get("notes", "")).strip()
            from app.modules.payments.service import PaymentsService
            from app.modules.payments.schemas_validation import PaymentFormSchema
            schema = PaymentFormSchema(client_id=client_id, amount=amount, payment_type=payment_type, notes=notes)
            async with session_maker() as session:
                service = PaymentsService(session)
                res = await service.create_payment_from_form(schema)
                await session.commit()
            return {"success": True, "payment_id": res[0]}

    elif func_name == "delete_operation":
            tx_kind = func_args.get("tx_kind")
            tx_id = int(func_args.get("tx_id"))
            success = False
            async with session_maker() as session:
                if tx_kind in ("sale_finished", "sale_raw", "sale"):
                    from app.modules.sales.service import SalesService
                    service = SalesService(session)
                    kind = "finished"
                    if tx_kind == "sale_raw":
                        kind = "raw"
                    elif tx_kind == "sale_finished":
                        kind = "finished"
                    else:
                        before_finished = await service.sale_repo.get_sale_detail("finished", tx_id)
                        if not before_finished:
                            kind = "raw"
                    success = await service.delete_sale_by_id(kind, tx_id)
                elif tx_kind == "purchase":
                    from app.modules.purchases.service import PurchaseService
                    service = PurchaseService(session)
                    success = await service.delete_purchase_by_id(tx_id)
                elif tx_kind == "payment":
                    from app.modules.payments.service import PaymentsService
                    service = PaymentsService(session)
                    success = await service.delete_payment_by_id(tx_id)
                if success:
                    await session.commit()
            if not success:
                return {"error": f"Opération {tx_kind} {tx_id} introuvable."}
            return {"success": True, "message": f"Opération {tx_kind} {tx_id} supprimée."}

    elif func_name == "add_expense":
            category = str(func_args.get("category", "")).strip().lower()
            amount = sanitize_numeric(func_args.get("amount"))
            description = str(func_args.get("description", "")).strip()
            payment_method = str(func_args.get("payment_method", "cash")).strip().lower()
    
            # Normalize category using shared constant
            if category in EXPENSE_CATEGORY_MAP:
                category = EXPENSE_CATEGORY_MAP[category]
            elif category not in _ALLOWED_EXPENSE_CATEGORIES:
                # Leave it as is so ExpenseCreateSchema validation fails naturally
                pass
    
            # Normalize payment method
            method_map = {
                "espèces": "cash", "espèce": "cash", "especes": "cash", "espece": "cash", "cash": "cash",
                "chèque": "cheque", "cheque": "cheque",
                "virement": "virement", "ccp": "virement",
                "autre": "autre"
            }
            payment_method = method_map.get(payment_method, "cash")
    
            from app.modules.expenses.schemas_validation import ExpenseCreateSchema
            import datetime
            schema = ExpenseCreateSchema(
                date=datetime.date.today(),
                category=category,
                description=description,
                amount=amount,
                payment_method=payment_method
            )
            from app.modules.expenses.service import add_expense
            async with session_maker() as session:
                expense_id = await add_expense(
                    db=session,
                    date=schema.date.isoformat(),
                    category=schema.category,
                    description=schema.description,
                    amount=schema.amount,
                    method=schema.payment_method
                )
                await session.commit()
            return {"success": True, "message": "Dépense enregistrée.", "expense_id": expense_id}

    elif func_name == "modify_expense":
            expense_id = int(func_args.get("expense_id"))
            category = func_args.get("category")
            if category:
                category = EXPENSE_CATEGORY_MAP.get(str(category).strip().lower(), str(category).strip().lower())
            amount = func_args.get("amount")
            if amount is not None:
                amount = sanitize_numeric(amount)
            description = func_args.get("description")
            if description:
                description = str(description).strip()
            from app.modules.expenses.service import get_expense, modify_expense
            async with session_maker() as session:
                db_exp = await get_expense(session, expense_id)
                if not db_exp:
                    return {"error": f"Dépense ID {expense_id} introuvable."}
                new_date = db_exp.date
                new_category = category if category is not None else db_exp.category
                new_amount = amount if amount is not None else float(db_exp.amount)
                new_description = description if description is not None else db_exp.description
                new_method = db_exp.payment_method
                await modify_expense(
                    db=session,
                    expense_id=expense_id,
                    date=new_date,
                    category=new_category,
                    description=new_description,
                    amount=new_amount,
                    method=new_method
                )
                await session.commit()
            return {"success": True, "message": f"Dépense {expense_id} modifiée."}

    elif func_name == "delete_expense":
            expense_id = int(func_args.get("expense_id"))
            from app.modules.expenses.service import remove_expense
            success = False
            async with session_maker() as session:
                success = await remove_expense(db=session, expense_id=expense_id)
                if success:
                    await session.commit()
            if not success:
                return {"error": f"Dépense {expense_id} introuvable."}
            return {"success": True, "message": f"Dépense {expense_id} supprimée."}

    elif func_name == "add_supplier_payment":
            supplier_id = int(func_args.get("supplier_id"))
            amount = sanitize_numeric(func_args.get("amount"))
            payment_type = str(func_args.get("payment_type", "versement")).strip().lower()
            if payment_type not in ("versement", "avance"):
                payment_type = "versement"
            notes = str(func_args.get("notes", "")).strip()
            purchase_id = func_args.get("purchase_id")
            if purchase_id:
                purchase_id = int(purchase_id)
            import datetime
            from sqlmodel import text
            async with session_maker() as session:
                # Verify supplier exists
                supplier_exists = (await session.execute(
                    text("SELECT id FROM suppliers WHERE id = :sid"), {"sid": supplier_id}
                )).fetchone()
                if not supplier_exists:
                    return {"error": f"Fournisseur ID {supplier_id} introuvable."}
                if amount <= 0:
                    return {"error": "Le montant du versement doit être supérieur à 0."}
                result = await session.execute(
                    text("""
                        INSERT INTO supplier_payments (supplier_id, purchase_id, payment_type, amount, payment_date, notes)
                        VALUES (:sid, :pid, :ptype, :amount, :pdate, :notes)
                        RETURNING id
                    """),
                    {
                        "sid": supplier_id,
                        "pid": purchase_id,
                        "ptype": payment_type,
                        "amount": amount,
                        "pdate": datetime.date.today().isoformat(),
                        "notes": notes,
                    }
                )
                payment_row = result.fetchone()
                await session.commit()
            payment_id = payment_row[0] if payment_row else None
            return {
                "success": True,
                "payment_id": payment_id,
                "message": f"Versement fournisseur de {amount:.2f} DA enregistré (ID: {payment_id})."
            }

    elif func_name == "get_print_link":
        dt = func_args.get("doc_type", "").lower()
        item_id = int(func_args.get("item_id"))
        allowed = {
            "sale_finished": f"/print/sale_finished/{item_id}",
            "sale_raw": f"/print/sale_raw/{item_id}",
            "purchase": f"/print/purchase/{item_id}",
            "payment": f"/print/payment/{item_id}",
            "production": f"/print/production/{item_id}",
            "client_history": f"/contacts/clients/{item_id}/print-history"
        }
        url = allowed.get(dt)
        if url:
            return {
                "print_url": url,
                "pdf_url": f"{url}?format=pdf",
                "message": f"Voici les liens d'impression :\n- [Imprimer/Voir]({url})\n- [Télécharger en PDF]({url}?format=pdf)"
            }
        return {"error": f"Type de document '{dt}' non supporté pour l'impression."}

    elif func_name == "get_export_link":
        import urllib.parse
        et = func_args.get("export_type", "").lower().strip()
        date_from = func_args.get("date_from", "").strip()
        date_to = func_args.get("date_to", "").strip()
        
        if et == "clients":
            url = "/api/v1/clients/export"
            return {
                "export_url": url,
                "message": f"Voici le lien pour exporter la liste des clients en CSV :\n- [Télécharger l'export Clients]({url})"
            }
        elif et == "reports":
            params = {}
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
            url = f"/reports/export-csv{query_str}"
            return {
                "export_url": url,
                "message": f"Voici le lien pour exporter le rapport global en CSV :\n- [Télécharger le Rapport]({url})"
            }
        elif et == "audit":
            params = {}
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            
            af = func_args.get("audit_filters") or {}
            if af.get("actor"):
                params["actor"] = af["actor"].strip()
            if af.get("action"):
                params["action"] = af["action"].strip()
            if af.get("entity_type"):
                params["entity_type"] = af["entity_type"].strip()
            if af.get("status"):
                params["status"] = af["status"].strip()
                
            query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
            url = f"/admin/audit/export{query_str}"
            return {
                "export_url": url,
                "message": f"Voici le lien pour exporter les journaux d'audit en CSV :\n- [Télécharger l'Audit]({url})"
            }
        elif et == "diagnostic":
            url = "/admin/system-status/export"
            return {
                "export_url": url,
                "message": f"Voici le lien pour exporter le rapport de diagnostic système en JSON :\n- [Télécharger le Rapport Diagnostic]({url})"
            }
            
        return {"error": f"Type d'export '{et}' non reconnu."}

    elif func_name == "create_invoice_document":
        client_id = func_args.get("client_id")
        if client_id:
            client_id = int(client_id)
        notes = str(func_args.get("notes", "")).strip()
        sale_date_str = func_args.get("sale_date")
        
        from datetime import datetime, date
        sale_date = date.today()
        if sale_date_str:
            try:
                sale_date = datetime.strptime(sale_date_str, "%Y-%m-%d").date()
            except Exception:
                return {"error": "Format de date invalide (sale_date). Utilisez YYYY-MM-DD."}

        lines_input = func_args.get("lines") or []
        if not lines_input:
            return {"error": "Une facture doit comporter au moins une ligne."}

        from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema
        lines = []
        for line in lines_input:
            item_key = line.get("item_key")
            quantity = sanitize_numeric(line.get("quantity"))
            unit = str(line.get("unit", "kg")).strip().lower()
            unit_price = sanitize_numeric(line.get("unit_price"))
            custom_item_name = str(line.get("custom_item_name", "")).strip()
            lines.append(
                SaleLineSchema(
                    item_key=item_key,
                    quantity=quantity,
                    unit=unit,
                    unit_price=unit_price,
                    custom_item_name=custom_item_name
                )
            )

        schema = SaleFormSchema(client_id=client_id, notes=notes, lines=lines, sale_date=sale_date)
        from app.modules.sales.service import SalesService
        async with session_maker() as session:
            service = SalesService(session)
            res = await service.create_sale_from_form(schema)
            await session.commit()

        doc_id = res.get("document_id") or res.get("first_line_id")
        doc_type = res.get("print_doc_type") or "sale_document"
        print_url = f"/print/{doc_type}/{doc_id}"
        return {
            "success": True,
            "message": f"Facture créée avec succès pour {len(lines)} ligne(s).",
            "document_id": doc_id,
            "print_url": print_url,
            "pdf_url": f"{print_url}?format=pdf"
        }

    elif func_name == "generate_quote":
        client_name = func_args.get("client_name") or "Client Proforma"
        lines_input = func_args.get("lines") or []
        notes = str(func_args.get("notes", "")).strip()

        lines_out = []
        total = 0.0
        for line in lines_input:
            item_name = line.get("item_name") or line.get("item_key") or "Article"
            quantity = sanitize_numeric(line.get("quantity"))
            unit = str(line.get("unit", "kg")).strip().lower()
            unit_price = sanitize_numeric(line.get("unit_price"))
            line_total = round(quantity * unit_price, 2)
            total += line_total
            lines_out.append({
                "item_name": item_name,
                "quantity": quantity,
                "unit": unit,
                "unit_price": unit_price,
                "total": line_total
            })

        return {
            "success": True,
            "client_name": client_name,
            "lines": lines_out,
            "total": total,
            "notes": notes,
            "message": f"Devis proforma généré avec succès pour un montant total de {total:,.2f} DA."
        }

    elif func_name == "get_stock_status":
        product_type = str(func_args.get("product_type", "all")).strip().lower()
        product_name = str(func_args.get("product_name", "")).strip().lower()

        from sqlmodel import select
        from app.core.models import FinishedProduct, RawMaterial

        finished_list = []
        raw_list = []

        async with session_maker() as session:
            if product_type in ("finished", "all"):
                stmt = select(FinishedProduct)
                if product_name:
                    stmt = stmt.where(FinishedProduct.name.like(f"%{product_name}%"))
                res = await session.execute(stmt)
                for item in res.scalars().all():
                    finished_list.append({
                        "id": item.id,
                        "name": item.name,
                        "stock_qty": float(item.stock_qty),
                        "unit": getattr(item, "default_unit", getattr(item, "unit", "kg")),
                        "avg_cost": float(item.avg_cost),
                        "price": float(getattr(item, "sale_price", getattr(item, "price", 0))),
                        "alert_threshold": float(item.alert_threshold or 0),
                        "is_low_stock": float(item.stock_qty) <= float(item.alert_threshold or 0)
                    })
            if product_type in ("raw", "all"):
                stmt = select(RawMaterial)
                if product_name:
                    stmt = stmt.where(RawMaterial.name.like(f"%{product_name}%"))
                res = await session.execute(stmt)
                for item in res.scalars().all():
                    raw_list.append({
                        "id": item.id,
                        "name": item.name,
                        "stock_qty": float(item.stock_qty),
                        "unit": item.unit,
                        "avg_cost": float(item.avg_cost),
                        "alert_threshold": float(item.alert_threshold or 0),
                        "is_low_stock": float(item.stock_qty) <= float(item.alert_threshold or 0)
                    })

        return {
            "success": True,
            "finished_products": finished_list,
            "raw_materials": raw_list,
            "low_stock_alert": any(p["is_low_stock"] for p in finished_list) or any(r["is_low_stock"] for r in raw_list)
        }

    elif func_name == "get_payment_status":
        client_id = func_args.get("client_id")
        document_id = func_args.get("document_id")
        if client_id:
            client_id = int(client_id)
        if document_id:
            document_id = int(document_id)

        from sqlmodel import select
        from app.core.models import Payment, Client
        from app.core.models_pkg.sales import SaleDocument

        payments_list = []
        client_info = None
        invoice_info = None

        async with session_maker() as session:
            if client_id:
                cl_obj = await session.get(Client, client_id)
                if cl_obj:
                    client_info = {
                        "id": cl_obj.id,
                        "name": cl_obj.name,
                        "balance": float(cl_obj.balance or 0)
                    }
            if document_id:
                doc_obj = await session.get(SaleDocument, document_id)
                if doc_obj:
                    invoice_info = {
                        "id": doc_obj.id,
                        "client_id": doc_obj.client_id,
                        "total": float(doc_obj.total or 0),
                        "amount_paid": float(doc_obj.amount_paid or 0),
                        "balance_due": float(doc_obj.balance_due or 0)
                    }

            # Fetch payments
            stmt = select(Payment)
            if client_id:
                stmt = stmt.where(Payment.client_id == client_id)
            if document_id:
                stmt = stmt.where(Payment.sale_id == document_id)

            res = await session.execute(stmt)
            for item in res.scalars().all():
                payments_list.append({
                    "id": item.id,
                    "client_id": item.client_id,
                    "amount": float(item.amount),
                    "payment_type": item.payment_type,
                    "payment_date": str(item.payment_date),
                    "notes": item.notes
                })

        return {
            "success": True,
            "client": client_info,
            "invoice": invoice_info,
            "payments": payments_list
        }

    elif func_name == "get_financial_report":
        from datetime import datetime, date
        start_date_str = func_args.get("start_date")
        end_date_str = func_args.get("end_date")

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else date(date.today().year, date.today().month, 1)
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else date.today()
        except Exception:
            return {"error": "Format de date invalide. Utilisez YYYY-MM-DD."}

        from sqlmodel import select, func
        from app.core.models import Sale, Purchase, Expense

        async with session_maker() as session:
            # Sales total
            sales_res = await session.execute(
                select(func.sum(Sale.total)).where(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
            )
            sales_total = float(sales_res.scalar() or 0)

            # Purchases total
            purchases_res = await session.execute(
                select(func.sum(Purchase.total)).where(Purchase.purchase_date >= start_date, Purchase.purchase_date <= end_date)
            )
            purchases_total = float(purchases_res.scalar() or 0)

            # Expenses total
            expenses_res = await session.execute(
                select(func.sum(Expense.amount)).where(Expense.date >= start_date, Expense.date <= end_date)
            )
            expenses_total = float(expenses_res.scalar() or 0)

        net_profit = sales_total - purchases_total - expenses_total

        return {
            "success": True,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "total_sales": sales_total,
            "total_purchases": purchases_total,
            "total_expenses": expenses_total,
            "net_profit": net_profit
        }

    return None

