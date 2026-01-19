import subprocess
import time
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

scripts_to_run = [
    os.path.join("process", "notification_manager.py"),
    os.path.join("process", "data_collector_consumer.py"),
    os.path.join("process", "insulin_pump_actuator.py"),
    os.path.join("process", "glucose_sensor_producer.py"),
    os.path.join("dashboard", "web_dashboard.py")

]

processes = []


def run_system():
    print(f"📂 Cartella di base rilevata: {BASE_DIR}")
    print("🚀 Avvio del sistema Glicemia Monitor IoT...")

    missing_files = []
    for script_rel in scripts_to_run:
        full_path = os.path.join(BASE_DIR, script_rel)
        if not os.path.exists(full_path):
            missing_files.append(script_rel)

    if missing_files:
        print("\n❌ ERRORE: Non riesco a trovare questi file:")
        for f in missing_files:
            print(f"   - {f}")
        print(
            "\n⚠️  Assicurati di aver salvato questo script 'start_system.py' nella cartella principale del progetto,")
        print("    accanto al file 'README.md' e alla cartella 'process'.")
        input("Premi INVIO per uscire...")
        return

    try:
        for script_rel in scripts_to_run:
            script_path = os.path.join(BASE_DIR, script_rel)
            print(f"   ▶ Avvio {os.path.basename(script_path)}...")

            cmd = [sys.executable, script_path]

            if sys.platform == "win32":
                p = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=BASE_DIR)
            else:
                p = subprocess.Popen(cmd, cwd=BASE_DIR)

            processes.append(p)
            time.sleep(1.5)

        print("\n✅ Tutto il sistema è operativo!")
        print("Premi CTRL+C in questo terminale per chiudere tutto.")

        # Loop infinito per tenere vivo lo script padre
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Arresto del sistema in corso...")
        for p in processes:
            p.terminate()
        print("Sistema spento correttamente.")


if __name__ == "__main__":
    run_system()