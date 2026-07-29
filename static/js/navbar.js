window.addEventListener("scroll",function(){

    const navbar=document.querySelector(".custom-navbar");

    if(window.scrollY>40){

        navbar.classList.add("scrolled");

    }

    else{

        navbar.classList.remove("scrolled");

    }

});