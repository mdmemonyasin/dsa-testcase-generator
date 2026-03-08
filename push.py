from AWS_lambda import push

# push("question-3c9951ab-4f22-4d22-93dc-d15b8a702e14", "http://localhost:8080/api/questionBank/question/internal/save-test-cases-and-driver-code", "606ed6954bbb886956db587b")

question_id = "question-43089dee-2b28-4e0d-acb5-fbbabf30cb85"
push(question_id, "http://localhost:8080/api/questionBank/question/internal/save-test-cases-and-driver-code", "606ed6954bbb886956db587b")