#!/bin/sh
# Full device-auth driver: poll -> artifact -> PKCE exchange -> final tokens
CID='app_EMoamEEZ73f0CkXaXp7hrann'
RU='http://localhost:1455/auth/callback'
GLOBAL_END=$(( $(date +%s) + 3600 ))
while [ $(date +%s) -lt $GLOBAL_END ]; do
  U=$(curl -s -X POST -H "content-type: application/json" -d "{\"client_id\":\"$CID\"}" --max-time 15 https://auth.openai.com/api/accounts/deviceauth/usercode)
  DA=$(echo "$U" | sed -n 's/.*"device_auth_id": *"\([^"]*\)".*/\1/p')
  UC=$(echo "$U" | sed -n 's/.*"user_code": *"\([^"]*\)".*/\1/p')
  [ -z "$UC" ] && { echo "$(date +%H:%M:%S) usercode fail" >> /tmp/poll_err.txt; sleep 20; continue; }
  echo "$UC" > /tmp/current_code.txt
  echo "code $UC" > /tmp/poll_status.txt
  POLL_END=$(( $(date +%s) + 840 ))
  while [ $(date +%s) -lt $POLL_END ] && [ $(date +%s) -lt $GLOBAL_END ]; do
    R=$(curl -s -X POST -H "content-type: application/json" -d "{\"device_auth_id\":\"$DA\",\"client_id\":\"$CID\",\"user_code\":\"$UC\"}" --max-time 15 https://auth.openai.com/api/accounts/deviceauth/token)
    case "$R" in
      *authorization_code*)
        echo "$R" > /tmp/auth_artifact.json
        AC=$(echo "$R" | sed -n 's/.*"authorization_code": *"\([^"]*\)".*/\1/p')
        CV=$(echo "$R" | sed -n 's/.*"code_verifier": *"\([^"]*\)".*/\1/p')
        T=$(curl -s -X POST -H "content-type: application/json" --max-time 20 https://auth.openai.com/oauth/token -d "{\"grant_type\":\"authorization_code\",\"code\":\"$AC\",\"code_verifier\":\"$CV\",\"client_id\":\"$CID\",\"redirect_uri\":\"$RU\"}")
        if echo "$T" | grep -q '"access_token"'; then
          echo "$T" > /tmp/token_result.json
          echo "FULL SUCCESS $(date +%H:%M:%S)" > /tmp/poll_status.txt
          exit 0
        else
          echo "$(date +%H:%M:%S) exchange failed: $T" >> /tmp/poll_err.txt
          echo "$T" > /tmp/exchange_fail.json
          exit 1
        fi
        ;;
      *pending*|*slow_down*) sleep 7;;
      *expired*) break;;
      *) echo "$(date +%H:%M:%S) $R" >> /tmp/poll_err.txt; sleep 9;;
    esac
  done
done
echo "GLOBAL TIMEOUT" > /tmp/poll_status.txt
