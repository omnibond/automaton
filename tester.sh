(date;
start=$(date +%s);
python3 tester.py 2>&1;
end=$(date +%s);
date;
echo tester took $((end-start)) seconds) | tee "${dir}/tester.log"
