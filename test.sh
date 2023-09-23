#! /bin/bash

echo "Embedding image:"
./main.py -f messages/a2.out messages/a.out messages/message -p pass -i images/test_1.png -E -v;
echo "Extracting from image:"
./main.py -e -p pass -i test_1_embedded.png;
echo "Checking files:"
file extracted_file_*;





echo "Embedding image:"
./main.py -f messages/a2.out messages/a.out messages/message -p pass -i images/test_I.png -E -v;
echo "Extracting from image:"
./main.py -e -p pass -i test_I_embedded.png;
echo "Checking files:"
file extracted_file_*;





echo "Embedding image:"
./main.py -f messages/a2.out messages/a.out messages/message -p pass -i images/test_I\;16.png -E -v;
echo "Extracting from image:"
./main.py -e -p pass -i test_I\;16_embedded.png;
echo "Checking files:"
file extracted_file_*;





echo "Embedding image:"
./main.py -f messages/a2.out messages/a.out messages/message -p pass -i images/test_L.png -E -v;
echo "Extracting from image:"
./main.py -e -p pass -i test_L_embedded.png;
echo "Checking files:"
file extracted_file_*;





echo "Embedding image:"
./main.py -f messages/a2.out messages/a.out messages/message -p pass -i images/test_LA.png -E -v;
echo "Extracting from image:"
./main.py -e -p pass -i test_LA_embedded.png;
echo "Checking files:"
file extracted_file_*;





echo "Embedding image:"
./main.py -f messages/a2.out messages/a.out messages/message -p pass -i images/test_P.png -E -v;
echo "Extracting from image:"
./main.py -e -p pass -i test_P_embedded.png;
echo "Checking files:"
file extracted_file_*;





echo "Embedding image:"
./main.py -f messages/a2.out messages/a.out messages/message -p pass -i images/test_RGB.png -E -v;
echo "Extracting from image:"
./main.py -e -p pass -i test_RGB_embedded.png;
echo "Checking files:"
file extracted_file_*;





echo "Embedding image:"
./main.py -f messages/a2.out messages/a.out messages/message -p pass -i images/test_RGBA.png -E -v;
echo "Extracting from image:"
./main.py -e -p pass -i test_RGBA_embedded.png;
echo "Checking files:"
file extracted_file_*;