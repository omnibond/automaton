x="$(grep output_dir tester.config)"
if [ "$x" = "" ]
then
    dir="$(pwd)"
else
    dir="$(grep output_dir tester.config | awk -F= '{ gsub(/ /, "", $2); gsub(/%%/, "%", $2); print $2 }')"
fi
dir="$(date "+${dir}")"
mkdir -p "${dir}"
(date;
python3 tester.py 2>&1;
date) | tee "${dir}/tester.log"
