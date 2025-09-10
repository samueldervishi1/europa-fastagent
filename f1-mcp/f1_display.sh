#!/bin/bash

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; MAGENTA='\033[0;35m'; CYAN='\033[0;36m'
WHITE='\033[1;37m'; NC='\033[0m'

clear
echo -e "\033[?25l"

fetch_driver_standings() {
    timeout 10s curl -s "https://f1api.dev/api/current/drivers-championship"
}

fetch_constructor_standings() {
    timeout 10s curl -s "https://f1api.dev/api/current/constructors-championship"
}

fetch_next_race() {
    timeout 10s curl -s "https://f1api.dev/api/current/next"
}

display_f1_data() {
    clear

    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}${WHITE}           🏎️  F1 CURRENT DRIVERS CHAMPIONSHIP  🏎️           ${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo -e "${YELLOW}Fetching driver standings...${NC}"
    drivers=$(fetch_driver_standings)
    echo -e "\033[1A\033[K"
    
    printf "${CYAN}%-4s %-25s %-22s %-8s${NC}\n" "POS" "DRIVER" "TEAM" "POINTS"
    echo -e "${BLUE}───────────────────────────────────────────────────────────────${NC}"

    echo "$drivers" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    drivers_list = data.get('drivers_championship', [])
    if not drivers_list:
        print('\033[1;31mError: No driver standings found.\033[0m')
    else:
        for d in drivers_list[:10]:
            pos = str(d.get('position', '?'))
            driver_info = d.get('driver', {})
            driver_name = f\"{driver_info.get('name','')} {driver_info.get('surname','')}\".strip()
            if not driver_name:
                driver_name = 'N/A'
            team_info = d.get('team', {})
            team_name = team_info.get('teamName', 'N/A')
            points = str(d.get('points', 0))
            if len(team_name) > 22:
                team_name = team_name[:19] + '...'
            color = '\033[1;33m' if pos == '1' else '\033[1;37m' if pos in ['2','3'] else '\033[0m'
            print(f'{color}{pos:>4} {driver_name:<25} {team_name:<22} {points:>8}\033[0m')
except Exception as e:
    print(f'\033[1;31mError: Unable to parse driver standings: {str(e)}\033[0m')
"

    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}${WHITE}        🛠️  F1 CURRENT CONSTRUCTORS CHAMPIONSHIP  🛠️        ${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo -e "${YELLOW}Fetching constructor standings...${NC}"
    constructors=$(fetch_constructor_standings)
    echo -e "\033[1A\033[K"
    
    printf "${CYAN}%-4s %-48s %-8s${NC}\n" "POS" "TEAM" "POINTS"
    echo -e "${BLUE}───────────────────────────────────────────────────────────────${NC}"

    echo "$constructors" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    constructors_list = data.get('constructors_championship', [])
    if not constructors_list:
        print('\033[1;31mError: No constructor standings found.\033[0m')
    else:
        for c in constructors_list[:10]:
            pos = str(c.get('position', '?'))
            team_info = c.get('team', {})
            team_name = team_info.get('teamName', 'N/A')
            points = str(c.get('points', 0))
            color = '\033[1;33m' if pos == '1' else '\033[1;37m' if pos in ['2','3'] else '\033[0m'
            print(f'{color}{pos:>4} {team_name:<48} {points:>8}\033[0m')
except Exception as e:
    print(f'\033[1;31mError: Unable to parse constructor standings: {str(e)}\033[0m')
"

    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}${WHITE}                      🏁  NEXT RACE  🏁                      ${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo -e "${YELLOW}Fetching next race...${NC}"
    next_race=$(fetch_next_race)
    echo -e "\033[1A\033[K"

    echo "$next_race" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    race_list = data.get('race', [])
    if race_list:
        race_info = race_list[0]
        schedule = race_info.get('schedule', {})
        race_schedule = schedule.get('race', {})
        name = race_info.get('raceName', 'N/A')
        circuit_info = race_info.get('circuit', {})
        circuit = circuit_info.get('circuitName', 'N/A')
        date = race_schedule.get('date', 'N/A')
        time = race_schedule.get('time', 'N/A')
        if time and time != 'N/A':
            time = time.replace('Z', ' UTC')
        
        print(f'\033[1;37m{name}\033[0m')
        print(f'\033[1;36mCircuit:\033[0m {circuit}')
        print(f'\033[1;36mRace Date:\033[0m {date} at {time}')
        
        # Show qualifying info if available
        qualy = schedule.get('qualy', {})
        if qualy.get('date'):
            qualy_date = qualy.get('date', 'N/A')
            qualy_time = qualy.get('time', 'N/A')
            if qualy_time and qualy_time != 'N/A':
                qualy_time = qualy_time.replace('Z', ' UTC')
            print(f'\033[1;36mQualifying:\033[0m {qualy_date} at {qualy_time}')
    else:
        print('\033[1;31mError: No next race info found.\033[0m')
except Exception as e:
    print(f'\033[1;31mError: Unable to fetch next race info: {str(e)}\033[0m')
"

    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}Updated: ${WHITE}$(date '+%Y-%m-%d %H:%M:%S')${NC}   ${MAGENTA}Source: ${WHITE}f1api.dev${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

main() {
    while true; do
        display_f1_data
        echo -e "${CYAN}Refreshing in 5 minutes... (Press Ctrl+C to exit)${NC}"
        sleep 300
    done
}

main