#!/usr/bin/env python3
"""
Seed script to populate initial Internet Access Plans and demo vouchers (fichas).
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, Base, SessionLocal
from app.models import Plan, Voucher, VoucherStatus

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if plans already exist
        if db.query(Plan).count() > 0:
            print("Database already contains plans. Skipping seed.")
            return

        print("Seeding initial internet plans and sample vouchers...")

        # 1. Create Default Plans
        plans_data = [
            {"name": "15 Minutos Rápido", "duration": 15, "price": 0.25, "desc": "Para enviar mensajes y consultas rápidas."},
            {"name": "1 Hora de Conexión", "duration": 60, "price": 0.50, "desc": "Navegación fluida y redes sociales."},
            {"name": "3 Horas Continuas", "duration": 180, "price": 1.00, "desc": "Ideal para trabajar, videos y tareas."},
            {"name": "1 Día Completo (24 Horas)", "duration": 1440, "price": 2.50, "desc": "Acceso ilimitado por 24 horas continuas."},
            {"name": "1 Semana Ilimitada (7 Días)", "duration": 10080, "price": 10.00, "desc": "Plan semanal para estancias prolongadas."}
        ]

        created_plans = []
        for p in plans_data:
            plan = Plan(
                name=p["name"],
                duration_minutes=p["duration"],
                price=p["price"],
                description=p["desc"]
            )
            db.add(plan)
            created_plans.append(plan)

        db.commit()

        # 2. Create Sample Test Vouchers (Fichas)
        sample_pins = [
            {"pin": "123456", "plan": created_plans[1]}, # 1 hora
            {"pin": "654321", "plan": created_plans[1]}, # 1 hora
            {"pin": "777888", "plan": created_plans[2]}, # 3 horas
            {"pin": "999000", "plan": created_plans[3]}, # 24 horas
        ]

        for s in sample_pins:
            v = Voucher(
                pin=s["pin"],
                plan_id=s["plan"].id,
                duration_minutes=s["plan"].duration_minutes,
                status=VoucherStatus.AVAILABLE
            )
            db.add(v)

        db.commit()

        print("\n========================================================")
        print(" [ÉXITO] Planes de Internet y Fichas Demo Creadas:")
        for s in sample_pins:
            print(f"   PIN: {s['pin']} -> {s['plan'].name} (${s['plan'].price:.2f})")
        print("========================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    seed()
