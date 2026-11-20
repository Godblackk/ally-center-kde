#!/bin/sh

# 1. Detectar modelo de consola
modelo="Center ROG Ally X"
if [ -r /sys/devices/virtual/dmi/id/product_name ]; then
    read -r prod < /sys/devices/virtual/dmi/id/product_name
    case "$prod" in
        *"Ally X"*|*"RC72"*) modelo="Center ROG Ally X" ;;
        *"Ally"*|*"RC71"*)   modelo="Center ROG Ally" ;;
    esac
fi

# 2. Detectar cargador AC conectado
ac_conectado="false"
for f in /sys/class/power_supply/*; do
    if [ -r "$f/type" ] && [ -r "$f/online" ]; then
        read -r tipo < "$f/type"
        if [ "$tipo" = "Mains" ]; then
            read -r online < "$f/online"
            [ "$online" = "1" ] && ac_conectado="true"
            break
        fi
    fi
done

# 3. Buscar carpetas hwmon en un solo recorrido
cpu_rpm=0
gpu_rpm=0
temp=0
watts="0.0"

for h in /sys/class/hwmon/hwmon*; do
    [ -r "$h/name" ] || continue
    read -r nombre < "$h/name"
    case "$nombre" in
        asus)
            for n in 1 2; do
                if [ -r "$h/fan${n}_label" ] && [ -r "$h/fan${n}_input" ]; then
                    read -r lbl < "$h/fan${n}_label"
                    read -r rpm < "$h/fan${n}_input"
                    [ "$lbl" = "cpu_fan" ] && cpu_rpm="$rpm"
                    [ "$lbl" = "gpu_fan" ] && gpu_rpm="$rpm"
                fi
            done
            ;;
        k10temp)
            if [ -r "$h/temp1_input" ]; then
                read -r t_raw < "$h/temp1_input"
                temp=$((t_raw / 1000))
            fi
            ;;
        amdgpu)
            # Prioriza power1_input (instantáneo) y usa power1_average como respaldo
            p_file=""
            [ -r "$h/power1_input" ] && p_file="$h/power1_input"
            [ -z "$p_file" ] && [ -r "$h/power1_average" ] && p_file="$h/power1_average"
            if [ -n "$p_file" ]; then
                read -r uw < "$p_file"
                watts=$(awk -v u="$uw" 'BEGIN { printf "%.1f", u / 1000000.0 }')
            fi
            ;;
    esac
done

# 4. Perfil de energía activo
perfil_json=""
if [ -r /sys/firmware/acpi/platform_profile ]; then
    read -r p_str < /sys/firmware/acpi/platform_profile
    case "$p_str" in
        low-power|quiet) perfil_json=', "perfil": 0' ;;
        balanced)        perfil_json=', "perfil": 1' ;;
        performance)     perfil_json=', "perfil": 2' ;;
    esac
fi

# 5. TDP actual
tdp_json=""
spl_path="/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl1_spl/current_value"
if [ -r "$spl_path" ]; then
    read -r w_actual < "$spl_path"
    max_w=25
    [ "$ac_conectado" = "true" ] && max_w=30
    [ "$w_actual" -lt 7 ] 2>/dev/null && w_actual=7
    [ "$w_actual" -gt "$max_w" ] 2>/dev/null && w_actual=$max_w
    tdp_json=", \"tdp\": $w_actual"
fi

# 6. CPU Boost
boost_json=""
if [ -r /sys/devices/system/cpu/cpufreq/boost ]; then
    read -r b_val < /sys/devices/system/cpu/cpufreq/boost
    if [ "$b_val" = "1" ]; then
        boost_json=', "boost": true'
    else
        boost_json=', "boost": false'
    fi
fi

# 7. Cuidado de Batería (80%)
bat_json=""
bat_path="/sys/class/power_supply/BAT0/charge_control_end_threshold"
if [ -r "$bat_path" ]; then
    read -r bat_val < "$bat_path"
    if [ "$bat_val" -le 85 ] 2>/dev/null; then
        bat_json=', "bateria_80": true'
    else
        bat_json=', "bateria_80": false'
    fi
fi

# Salida JSON idéntica a ally_center.py
printf '{"modelo": "%s", "cpu_rpm": %d, "gpu_rpm": %d, "temp": %d, "watts": "%s", "ac_conectado": %s%s%s%s%s}\n' \
    "$modelo" "$cpu_rpm" "$gpu_rpm" "$temp" "$watts" "$ac_conectado" \
    "$perfil_json" "$tdp_json" "$boost_json" "$bat_json"
