1. run flowise first from docker wait until cpu usage become something 0.XX
2. run n8n second from docker wait until cpu usage become something 0.XX
3. Unzip the folder
4. in flowise,Go to setting icon (on top right corner) click import and select flowise json file form the unzipped folder.
5. in n8n, create a new workflow, then click on 3 dots on top right corner and then select import form file. Select n8n json file
6. open vs code, click on files , then open folder , then select unzipped folder
7. open app.py file and run it using this in terminal: streamlit run app.py
8. Done for normal user

For Automation:
7. open api_server.py file, run it
8. open n8n dashboard, execute workflow
9. open new terminal in same dir, run this code:

$filePath = "test_doc.jpg"
>> $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
>> $fileBase64 = [Convert]::ToBase64String($fileBytes)
>> 
>> $body = @{
>>     image_base64 = $fileBase64
>>     file_extension = ".jpg"
>> } | ConvertTo-Json
>> 
>> Invoke-RestMethod -Uri "http://localhost:5678/webhook-test/analyze" `
>>   -Method POST `
>>   -ContentType "application/json" `
>>   -Body $body 
