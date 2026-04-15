//send api login request
async function login(){
    try{
        const log_user = document.getElementById("log_username").value;
        const log_pass = document.getElementById("log_password").value;
        const url = 'http://localhost:8080/auth/login';

        const user_data={
            username: log_user,
            password: log_pass
        };

        const response = await fetch(url, { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(user_data)
        });
        //if no error, store session token in localStorage and load home page
        if(response.ok){
            window.location.href = 'http://localhost:8080/home';
            const data = await response.json(); 
            const token = data.token;   
            localStorage.setItem('session_token', token)
        }else{
            const data = await response.json(); 
            const error = data.error;
            alert(`Error: ${error}`);
            console.error(`Error: ${response.status} ${response.statusText}`);
        }
    }catch(error){
        console.error("Error:", error);
    }
    return false;
}

//send api signup request
async function signup(){
    try{
        const sign_user = document.getElementById("sign_username").value;
        const sign_pass = document.getElementById("sign_password").value;
        const url = 'http://localhost:8080/auth/signup';

        const user_data={
            username: sign_user,
            password: sign_pass
        };

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(user_data)
        });
        //if no error, load login page & alert of success
        if(response.ok){
            window.location.href = 'http://localhost:8080/login';
            const data = await response.json(); 
            const msg = data.message;
            alert(msg);
            console.log(msg)
        }else{
            const data = await response.json(); 
            const error = data.error;
            alert(`Error: ${error}`);
            console.error(`Error: ${response.status} ${response.statusText}`);
        }
    }catch(error){
        console.error("Error:", error);
    }
    return false;
}

//send api doc upload request
async function upload(){
    try{
        var input = document.querySelector('input[type="file"]');
        const url = 'http://localhost:8080/documents';
        //retrieve token from localStorage for header
        const token = localStorage.getItem('session_token');

        const formData = new FormData();
        formData.append("file", input.files[0]);

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        //if no error, alert of success
        if(response.ok){
            const data = await response.json(); 
            const msg = data.message;
            alert(msg);
            console.log(msg)
        }else{
            const data = await response.json(); 
            const error = data.error;
            alert(`Error: ${error}`);
            console.error(`Error: ${response.status} ${response.statusText}`);
        }
    }catch(error){
        console.error("Error:", error);
    }
    return false;
}

//send api doc view request & display response
async function view(){
    try{
        const url = 'http://localhost:8080/documents';
        //retrieve token from localStorage for header
        const token = localStorage.getItem('session_token');

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        //if no error, display response in new window
        if(response.ok){
            const data = await response.json(); 
            const formattedJson = JSON.stringify(data, null, 2);
            const newWindow = window.open();
            newWindow.document.write(`
                <html>
                    <head><title>Documents</title></head>
                    <body>
                        <pre>${formattedJson}</pre>
                    </body>
                </html>
            `);
        }else{
            console.error(`Error: ${response.status} ${response.statusText}`);
        }
    }catch(error){
        console.error("Error:", error);
    }
    return false;
}

//send api doc delete request
async function remove(){
    try{
        const document_id = document.getElementById("doc_id").value;
        const url = `http://localhost:8080/documents/${document_id}`;
        const token = localStorage.getItem('session_token');

        const response = await fetch(url, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        //if no error, alert of success
        if(response.ok){
            const data = await response.json(); 
            const msg = data.message;
            alert(msg);
            console.log(msg)
        }else{
            const data = await response.json(); 
            const error = data.error;
            alert(`Error: ${error}`);
            console.error(`Error: ${response.status} ${response.statusText}`);
        }
    }catch(error){
        console.error("Error:", error);
    }
    return false;
}

//send api doc search request & display response
async function search(){
    try{
        const term = document.getElementById("term").value;
        const url = new URL('http://localhost:8080/search');
        const token = localStorage.getItem('session_token');
        url.searchParams.append('q', term);

        const response = await fetch(url.toString(), {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        //if no error, display response in new window
        if(response.ok){
            const data = await response.json(); 
            const formattedJson = JSON.stringify(data, null, 2);
            const newWindow = window.open();
            newWindow.document.write(`
                <html>
                    <head><title>Documents</title></head>
                    <body>
                        <pre>${formattedJson}</pre>
                    </body>
                </html>
            `);
        }else{
            const data = await response.json(); 
            const error = data.error;
            alert(`Error: ${error}`);
            console.error(`Error: ${response.status} ${response.statusText}`);
        }
    }catch(error){
        console.error("Error:", error);
    }
    return false;
}

//prevent default event behavior
const validation = event => {
        event.preventDefault();
}

