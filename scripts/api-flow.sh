#!/bin/sh
# End-to-end API walkthrough through the nginx /api proxy:
# doctor -> patients -> booking -> double booking (409) -> check-in -> call in
# -> queue -> complete -> invalid transition (409) -> stats -> clean-up.
#
#   scripts/api-flow.sh                          # against http://localhost:3000/api
#   BASE_URL=http://carequeue.local/api scripts/api-flow.sh
#
# POSIX sh + curl only (no jq), so it also runs inside the curlimages/curl image.
set -eu

BASE_URL="${BASE_URL:-http://localhost:3000/api}"
RUN_ID="$(date +%s | tail -c 6)"   # keeps phone numbers unique between runs

# call METHOD PATH [JSON]: print the request and the response with its HTTP status.
call() {
  method="$1"; path="$2"; body="${3:-}"
  echo "--> $method /api$path ${body}"
  if [ -n "$body" ]; then
    RESP=$(curl -sS -X "$method" -H 'Content-Type: application/json' -d "$body" -w '\n%{http_code}' "$BASE_URL$path")
  else
    RESP=$(curl -sS -X "$method" -w '\n%{http_code}' "$BASE_URL$path")
  fi
  CODE=$(printf '%s\n' "$RESP" | tail -n 1)
  BODY=$(printf '%s\n' "$RESP" | sed '$d')
  echo "<-- HTTP $CODE ${BODY}"
  echo
}

# expect CODE: fail the walkthrough if the last call returned something else.
expect() {
  if [ "$CODE" != "$1" ]; then echo "!! expected HTTP $1, got $CODE" >&2; exit 1; fi
}

# Value of the FIRST "key": in the last response body (top-level id comes first).
field() { printf '%s' "$BODY" | grep -o "\"$1\":\"\{0,1\}[0-9A-Za-z:-]*" | head -n 1 | sed 's/^[^:]*://; s/"//g'; }

echo "== CareQueue API flow against $BASE_URL"
call GET /info; expect 200
call GET /stats/today; expect 200
TODAY=$(field date)

echo "== 1. Register an evening-clinic doctor and two patients"
call POST /doctors '{"full_name":"Dr. Nikhil Bose","specialty":"General Medicine","room":"E-2","slot_minutes":15,"start_time":"08:00","end_time":"23:45"}'
expect 201; DOC=$(field id)
call POST /patients "{\"full_name\":\"Farhan Qureshi\",\"phone\":\"+91 91234 ${RUN_ID}\",\"date_of_birth\":\"1990-08-14\",\"gender\":\"male\"}"
expect 201; P1=$(field id)
call POST /patients "{\"full_name\":\"Lakshmi Pillai\",\"phone\":\"81234${RUN_ID}\",\"date_of_birth\":\"1968-02-03\",\"gender\":\"female\"}"
expect 201; P2=$(field id)
call POST /patients "{\"full_name\":\"Duplicate Phone\",\"phone\":\"81234${RUN_ID}\",\"date_of_birth\":\"1990-01-01\",\"gender\":\"other\"}"
expect 409
call POST /patients '{"full_name":"Bad Phone","phone":"12345","date_of_birth":"1990-01-01","gender":"other"}'
expect 422

echo "== 2. Slot grid for today ($TODAY): book the next two free slots"
call GET "/doctors/$DOC/slots?date=$TODAY"; expect 200
SLOT1=$(printf '%s' "$BODY" | grep -o '"time":"[0-9:]*","status":"free"' | sed -n '1s/"time":"\([0-9:]*\)".*/\1/p')
SLOT2=$(printf '%s' "$BODY" | grep -o '"time":"[0-9:]*","status":"free"' | sed -n '2s/"time":"\([0-9:]*\)".*/\1/p')
if [ -z "$SLOT2" ]; then echo "!! no free slots left today (clinic closes 23:45)" >&2; exit 1; fi
call POST /appointments "{\"patient_id\":$P1,\"doctor_id\":$DOC,\"appointment_date\":\"$TODAY\",\"slot_time\":\"$SLOT1\",\"reason\":\"High fever since last night\"}"
expect 201; A1=$(field id)
call POST /appointments "{\"patient_id\":$P2,\"doctor_id\":$DOC,\"appointment_date\":\"$TODAY\",\"slot_time\":\"$SLOT2\",\"reason\":\"Diabetes review\"}"
expect 201; A2=$(field id)

echo "== 3. Business rules: double booking, off-grid slot, past date"
call POST /appointments "{\"patient_id\":$P2,\"doctor_id\":$DOC,\"appointment_date\":\"$TODAY\",\"slot_time\":\"$SLOT1\"}"
expect 409
call POST /appointments "{\"patient_id\":$P2,\"doctor_id\":$DOC,\"appointment_date\":\"$TODAY\",\"slot_time\":\"23:50\"}"
expect 422
call POST /appointments "{\"patient_id\":$P2,\"doctor_id\":$DOC,\"appointment_date\":\"2020-01-01\",\"slot_time\":\"10:00\"}"
expect 422

echo "== 4. Visit workflow: check-in, call in, live queue, complete"
call PATCH "/appointments/$A1/status" '{"status":"checked_in"}'; expect 200
call PATCH "/appointments/$A2/status" '{"status":"checked_in"}'; expect 200
call PATCH "/appointments/$A1/status" '{"status":"in_consultation"}'; expect 200
call PATCH "/appointments/$A2/status" '{"status":"in_consultation"}'; expect 409
call GET "/queue?doctor_id=$DOC"; expect 200
call PATCH "/appointments/$A1/status" '{"status":"completed"}'; expect 200
call PATCH "/appointments/$A1/status" '{"status":"checked_in"}'; expect 409
call GET "/appointments?date=$TODAY&doctor_id=$DOC"; expect 200
call GET /stats/today; expect 200

echo "== 5. Updates and clean-up"
call PUT "/patients/$P2" "{\"full_name\":\"Lakshmi R. Pillai\",\"phone\":\"81234${RUN_ID}\",\"date_of_birth\":\"1968-02-03\",\"gender\":\"female\"}"
expect 200
call DELETE "/appointments/$A1"; expect 409
call PATCH "/appointments/$A2/status" '{"status":"no_show"}'; expect 200
call DELETE "/appointments/$A2"; expect 204
call DELETE "/patients/$P1"; expect 204
call DELETE "/patients/$P2"; expect 204
call DELETE "/doctors/$DOC"; expect 200
call GET "/doctors/$DOC"; expect 404

echo "== API flow finished: every response had the expected status code"
