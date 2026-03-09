from AWS_lambda import push

# push("question-3c9951ab-4f22-4d22-93dc-d15b8a702e14", "http://localhost:8080/api/questionBank/question/internal/save-test-cases-and-driver-code", "606ed6954bbb886956db587b")

question_id = "question-42486430-8ca6-467e-a5d4-a61600b6fccf"
push(question_id, "https://www.boardinfinity.com/cms-api/api/questionBank/question/internal/save-test-cases-and-driver-code", "606ed6954bbb886956db587b")