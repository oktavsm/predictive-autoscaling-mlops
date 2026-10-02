#!/usr/bin/env bash
# ==============================================================================
# CLI Control Helper for Titipin Continuous Traffic Generator
# ==============================================================================
# Usage:
#   ./manage_generator.sh status        # Cek status generator
#   ./manage_generator.sh logs          # Pantau log pergerakan trafik real-time
#   ./manage_generator.sh start         # Jalankan service
#   ./manage_generator.sh stop          # Hentikan service
#   ./manage_generator.sh restart       # Muat ulang service
#   ./manage_generator.sh trigger spike # Paksa langsung lonjakan spike flash-sale
#   ./manage_generator.sh trigger steady# Paksa trafik normal santai
#   ./manage_generator.sh trigger idle  # Paksa trafik 0 (momen sepi)
# ==============================================================================

SERVICE_NAME="titipin-traffic-generator"
BASE_DIR="/home/dev/titipin-traffic-generator"
OVERRIDE_FILE="${BASE_DIR}/force_state.txt"

ACTION="${1:-status}"

case "$ACTION" in
    status)
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    logs)
        sudo journalctl -u "$SERVICE_NAME" -f -o cat
        ;;
    start)
        sudo systemctl start "$SERVICE_NAME"
        echo "Traffic generator started."
        sudo systemctl status "$SERVICE_NAME" --no-pager | head -n 10
        ;;
    stop)
        sudo systemctl stop "$SERVICE_NAME"
        echo "Traffic generator stopped."
        ;;
    restart)
        sudo systemctl restart "$SERVICE_NAME"
        echo "Traffic generator restarted."
        ;;
    trigger)
        STATE="${2:-spike}"
        case "$STATE" in
            spike|anomaly|flash)
                echo "SPIKE" > "$OVERRIDE_FILE"
                echo "Triggered immediate FLASH_ANOMALY spike state."
                ;;
            idle|zero|quiet)
                echo "IDLE" > "$OVERRIDE_FILE"
                echo "Triggered immediate IDLE_SILENT state."
                ;;
            steady|normal)
                echo "STEADY" > "$OVERRIDE_FILE"
                echo "Triggered immediate STEADY_NORMAL state."
                ;;
            burst|busy)
                echo "BURST_BUSY" > "$OVERRIDE_FILE"
                echo "Triggered immediate BURST_BUSY state."
                ;;
            *)
                echo "Unknown trigger state: $STATE. Use: spike, idle, steady, burst"
                exit 1
                ;;
        esac
        ;;
    *)
        echo "Usage: $0 {status|logs|start|stop|restart|trigger [spike|idle|steady|burst]}"
        exit 1
        ;;
esac
