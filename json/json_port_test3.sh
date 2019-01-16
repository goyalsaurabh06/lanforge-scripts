#!/bin/bash
set -e
unset proxy
unset http_proxy
Q='"'
q="'"
S='*'
m=40
n=42
application_json="application/json"
accept_json="Accept: $application_json"
accept_html='Accept: text/html'
accept_text='Accept: text/plain'
#accept_any="'Accept: */*'" # just dont use
content_plain='Content-Type: text/plain'
content_json="Content-Type: $application_json"
headers="/var/tmp/headers.$$"
switches="-s -D $headers -o $result"
#switches='-sq'
data_file=/var/tmp/data.$$
result=/var/tmp/result.$$

function Kurl() {
   echo "======================================================================================="
   echo "curl $switches $@"
   echo "======================================================================================="
   curl $switches "$@" | json_pp
   echo ""
   echo "======================================================================================="
}

function Jurl() {
   echo "=J====================================================================================="
   echo "curl $switches -H $accept_json -H $content_json $@"
   echo "=J====================================================================================="
   curl $switches -H "$accept_json" -H "$content_json" -X POST "$@"
   echo ""
   echo "=J====================================================================================="
}

function Kuurl() {
   echo "URL: ${@:$#}"
   echo "" > $result
   echo "" > $headers
   #curl $switches  -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$@" ||:
   set -x
   curl "$@" ||:
   set +x
   grep 'HTTP/1.1 200' $headers || (echo "${@:$#}"; cat $headers)
}

#url="http://jed-f24m64-9119:8080"
url="http://127.0.0.1:8080"

function PortDown() {
   switches="-s -D $headers -o $result"
   echo "{\"shelf\":1,\"resource\":3,\"port\":\"$1\",\"current_flags\":1, \"interest\":8388610}" > $data_file
   Kuurl $switches -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$url/cli-json/set_port"
   sleep 0.3
   for f in `seq 1 10`; do
      echo "{\"shelf\":1,\"resource\":3,\"port\":\"$1\"}" > $data_file
      cat $data_file
      Kuurl $switches -H "$accept_json" -H "$content_json" -X POST -d"@$data_file" "$url/cli-json/nc_show_ports"
      sleep 0.5
      Kuurl $switches "$url/port/1/3/$1?fields=alias,ip,down"
      json_pp < $result || cat $result
      grep '"down".*true' $result && break || :
   done
}

function PortUp() {
   #set_port 1 3 sta3101 NA NA NA NA 0 NA NA NA NA 8388610
   echo "{\"shelf\":1,\"resource\":3,\"port\":\"$1\",\"current_flags\":0, \"interest\":8388610}" > $data_file
   curl $switches -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$url/cli-json/set_port"
   sleep 1
   for f in `seq 1 100`; do
      echo "{\"shelf\":1,\"resource\":3,\"port\":\"$1\"}" > $data_file
      #Jurl -d"@$data_file" "$url/cli-json/nc_show_ports"
      curl $switches -H "$accept_json" -H "$content_json" -X POST -d"@$data_file" "$url/cli-json/nc_show_ports"
      sleep 0.5
      curl $switches "$url/port/1/3/$1?fields=alias,ip,down"
      json_pp < $result || cat $result
      grep '"down".*false' $result && break || :
   done
}

function CxToggle() {
   echo "{\"test_mgr\":\"all\",\"cx_name\":\"$1\",\"cx_state\":\"$2\"}" > $data_file
   cat $data_file
   Kuurl $switches -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$url/cli-json/set_cx_state"
}

function CxCreate() { # alias, port
   echo "{\"alias\":\"$1-A\",\"shelf\":1,\"resource\":3,\"port\":\"$2\",\"type\":\"lf_udp\",\"ip_port\":\"AUTO\",\"is_rate_bursty\":\"NO\",\"min_rate\":164000,\"min_pkt\":-1,\"max_pkt\":0}" > $data_file
   cat $data_file
   Kuurl $switches -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$url/cli-json/add_endp"

   echo "{\"alias\":\"$1-B\",\"shelf\":1,\"resource\":2,\"port\":\"b2000\",\"type\":\"lf_udp\",\"ip_port\":\"AUTO\",\"is_rate_bursty\":\"NO\",\"min_rate\":64000,\"min_pkt\":-1,\"max_pkt\":0}" > $data_file
   cat $data_file
   Kuurl $switches -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$url/cli-json/add_endp"

   echo "{\"alias\":\"$1\",\"test_mgr\":\"default_tm\",\"tx_endp\":\"$1-A\",\"rx_endp\":\"$1-B\"}" > $data_file
   cat $data_file
   Kuurl $switches -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$url/cli-json/add_cx"

   echo "{\"endpoint\":\"$1-A\"}" > $data_file
   Kuurl $switches -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$url/cli-json/nc_show_endpoints"

   echo "{\"endpoint\":\"$1-B\"}" > $data_file
   Kuurl $switches -H "$accept_json" -H "$content_json" -X POST  -d"@$data_file" "$url/cli-json/nc_show_endpoints"
}

# create some cx
for eidcx in `seq $m $n` ; do
   CxCreate "udp-$eidcx" "sta$((3060 + $eidcx))"
   sleep 1
   Kuurl $switches  -H "$accept_json" "$url/endp/udp-$eidcx-A?fields=name,run"
   Kuurl $switches  -H "$accept_json" "$url/endp/udp-$eidcx-B?fields=name,run"
   Kuurl $switches  -H "$accept_json" "$url/cx/udp-$eidcx?fields=name,state"
done

sleep 5
while true; do
   for eidcx in `seq $m $n` ; do
      CxToggle "udp-$eidcx" "STOPPED"
      Kuurl $switches  -H "$accept_json" "$url/endp/udp-$eidcx-A?fields=name,run"
      Kuurl $switches  -H "$accept_json" "$url/endp/udp-$eidcx-B?fields=name,run"
      Kuurl $switches  -H "$accept_json" "$url/cx/udp-$eidcx?fields=name,state"
   done
   for sta in `seq 100 120`; do
      stb=$(( $sta + 3000))
      PortDown "sta$stb"
   done
   for sta in `seq 100 120`; do
      stb=$(( $sta + 3000))
      PortUp "sta$stb"
   done
   sleep 4
   for eidcx in `seq $m $n` ; do
      CxToggle "udp-$eidcx" "RUNNING"
      Kuurl $switches  -H "$accept_json" "$url/endp/udp-$eidcx-A?fields=name,run"
      Kuurl $switches  -H "$accept_json" "$url/endp/udp-$eidcx-B?fields=name,run"
      Kuurl $switches  -H "$accept_json" "$url/cx/udp-$eidcx?fields=name,state"
   done
   sleep 14
done

#
