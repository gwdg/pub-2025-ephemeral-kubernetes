for i in {1..50}; do   echo "Run $i";   ./rebuild-and-restart.sh && ./benchmark-deployment.sh;
    echo "Run $i completed";   sleep 10 # wait before starting the next run
done
