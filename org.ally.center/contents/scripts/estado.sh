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
            if [ "$temp" -eq 0 ] && [ -r "$h/temp1_input" ]; then
                read -r t_raw < "$h/temp1_input"
                temp=$((t_raw / 1000))
            fi
            ;;
        amdgpu)
            if [ -r "$h/temp1_input" ]; then
                read -r t_raw < "$h/temp1_input"
                temp=$((t_raw / 1000))
            fi
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

# 4. Perfil de energía activo (power-profiles-daemon + platform_profile)
perfil_json=""
p_str=""
if [ -r /var/lib/power-profiles-daemon/state.ini ]; then
    p_str=$(sed -n 's/^Profile=//p' /var/lib/power-profiles-daemon/state.ini)
fi
if [ -z "$p_str" ] && [ -r /sys/firmware/acpi/platform_profile ]; then
    read -r p_str < /sys/firmware/acpi/platform_profile
fi
case "$p_str" in
    low-power|quiet|power-saver) perfil_json=', "perfil": 0' ;;
    balanced) perfil_json=', "perfil": 1' ;;
    performance) perfil_json=', "perfil": 2' ;;
esac

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

# 8. Estado persistente desde /etc/ally-center.json (curva, modo_fan, tdp_boost, rgb)
extra_json=""
if [ -r /etc/ally-center.json ]; then
    json_raw=$(tr -d '\n\r ' < /etc/ally-center.json)
    # Extrae todo el contenido interno quitando la primera '{' y la última '}'
    inner="${json_raw#\{}"
    inner="${inner%\}}"
    [ -n "$inner" ] && extra_json=", $inner"
fi

# 9. Telemetría en vivo de batería (consumo total W y tiempo restante)
bat_pct=100
bat_watts="0.0"
bat_tiempo="AC"
if [ -d /sys/class/power_supply/BAT0 ]; then
    [ -r /sys/class/power_supply/BAT0/capacity ] && read -r bat_pct < /sys/class/power_supply/BAT0/capacity
    b_stat=""
    [ -r /sys/class/power_supply/BAT0/status ] && read -r b_stat < /sys/class/power_supply/BAT0/status
    e_now=0
    p_now=0
    [ -r /sys/class/power_supply/BAT0/energy_now ] && read -r e_now < /sys/class/power_supply/BAT0/energy_now
    [ -r /sys/class/power_supply/BAT0/power_now ] && read -r p_now < /sys/class/power_supply/BAT0/power_now

    if [ "$p_now" -gt 100000 ] 2>/dev/null; then
        bat_watts=$(awk -v p="$p_now" 'BEGIN { printf "%.1f", p / 1000000.0 }')
        if [ "$b_stat" = "Discharging" ] && [ "$e_now" -gt 0 ] 2>/dev/null; then
            mins=$(( (e_now * 60) / p_now ))
            hrs=$(( mins / 60 ))
            rem=$(( mins % 60 ))
            bat_tiempo="${hrs}h ${rem}m"
        elif [ "$b_stat" = "Charging" ]; then
            bat_tiempo="Cargando"
        fi
    else
        [ "$b_stat" = "Charging" ] && bat_tiempo="Cargando"
    fi
fi



# Salida JSON completa (hardware en vivo + configuración guardada)
printf '{"modelo": "%s", "cpu_rpm": %d, "gpu_rpm": %d, "temp": %d, "watts": "%s", "ac_conectado": %s, "bat_pct": %d, "bat_watts": "%s", "bat_tiempo": "%s"%s%s%s%s%s}\n' \
    "$modelo" "$cpu_rpm" "$gpu_rpm" "$temp" "$watts" "$ac_conectado" "$bat_pct" "$bat_watts" "$bat_tiempo" \
    "$extra_json" "$perfil_json" "$tdp_json" "$boost_json" "$bat_json"


