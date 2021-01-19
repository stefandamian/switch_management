function js_change(nr){
		if (document.getElementById('port'+nr).style.color==="white"){
			document.getElementById('port'+nr).style.border="2px solid black"
			document.getElementById('port'+nr).style.color="black"
		}
		else{
			document.getElementById('port'+nr).style.border="2px dotted rgb(51,51,255)"
			document.getElementById('port'+nr).style.color="white"
		}
		let numb=selected_ports()
		if (numb.length>0.5){
			document.getElementById('change').innerHTML="Change state for ports";
			document.getElementById('change_botton').style.display="inline-block";
			document.getElementById('change_botton').style.margin="15px 3px 3px 1px";
			document.getElementById('port_no_vlan').innerHTML="No vlan for ports";
			document.getElementById('change_botton_vlan').style.display="inline-block";
			document.getElementById('change_botton_vlan').style.margin="15px 3px 3px 1px";
			a=document.getElementsByClassName('change_botton_vlan_add')
			for(let i=0;i<a.length;i++){
				a[i].style.display="inline-block";
				a[i].style.margin="15px 3px 3px 1px";
			}
			document.getElementById('id_numbers').value=""
			let ret=""
			console.log(numb)
			for (let i=0;i<numb.length;i++){
				console.log(numb[i])
				ret+=String(numb[i])
				ret+=','
			}
			document.getElementById('id_numbers').value=ret
		}
		else{
			document.getElementById('change_botton').style.display="none";
			document.getElementById('change_botton_vlan').style.display="none";
			a=document.getElementsByClassName('change_botton_vlan_add')
			for(let i=0;i<a.length;i++){
				a[i].style.display="none"
			}
			document.getElementById('id_numbers').value=""
		}
		

	}
	function selected_ports(){
		let numbers=[]
		ports=document.getElementsByClassName('port')
		for (let i=0;i<ports.length;i++){
			if (ports[i].style.color==="white"){
				numbers.push(ports[i].id.slice(4))
			}
		}
		console.log(numbers)
		return numbers
	}
	function vlan_show(){
		document.getElementById('vlans_button1').style.display="none";
		document.getElementById('vlans_detail').style.display='initial';

	}
	function vlan_hide(){
		document.getElementById('vlans_button1').style.display="inline-block";
		document.getElementById('vlans_detail').style.display='none';

	}
	function hides(){
			document.getElementById('main_info').style.border='0px;';
			document.getElementById('vlans_button1').style.visibility = "hidden";
	}

	function form_vlan(){
		document.getElementById('want_sub').action="/switches/{{switch.id}}/port_no_vlan"
		document.getElementById('want_sub').submit();
	}

	function form_port(){
		
		document.getElementById('want_sub').action='/switches/{{switch.id}}/change_port_state'
		document.getElementById('want_sub').submit();
	}

	function form_to_vlan(VID){
		document.getElementById('want_sub').action="/switches/{{switch.id}}/"+VID+"/add_port"
		document.getElementById('want_sub').submit();
	}

	function show_vlan(my_vlan,vlans,nr){
		my_ports=vlans[my_vlan]
		console.log(vlans)
		console.log(my_vlan)
		console.log(my_ports)
		if (my_ports === undefined){
			for (let i=1;i<=nr;i++){
				document.getElementById('port'+i).style.backgroundColor="#c7c7c7"
			}
		}
		else{
			for (let i=1;i<=nr;i++){
				document.getElementById('port'+i).style.backgroundColor="#c7c7c7"
			}
			my_ports.forEach(gigel);
			function gigel(value, index, array){
				document.getElementById('port'+value).style.backgroundColor="#00e600"
			}
		}
	}

	function duplex_show(duplex,nr){
		console.log(duplex['HALF'])
		console.log(duplex['FULL'])
		for (let i=1;i<=nr;i++){
			document.getElementById('port'+i).style.backgroundColor="#c7c7c7"
		}
		if (duplex['FULL']!== undefined){
			duplex['FULL'].forEach(costel);
			function costel(value, index, array){
				document.getElementById('port'+value).style.backgroundColor="#00e600"
			}
		}
		if (duplex['HALF']!== undefined){
			duplex['HALF'].forEach(costel);
			function costel(value, index, array){
				document.getElementById('port'+value).style.backgroundColor="#FFBF00"
			}
		}
	}

	function print_ports(state,nr){
		console.log(state['up'])
		console.log(state['down'])
		console.log(state['admin_down'])
		for (let i=1;i<=nr;i++){
			document.getElementById('port'+i).style.backgroundColor="#FA5858"
		}
		if (state['up']!== undefined){
			state['up'].forEach(costel);
			function costel(value, index, array){
				document.getElementById('port'+value).style.backgroundColor="#00e600"
			}
		}
		if (state['down']!== undefined){
			state['down'].forEach(costel);
			function costel(value, index, array){
				document.getElementById('port'+value).style.backgroundColor="#FFBF00"
			}
		}
	}


/// tree
	var toggler = document.getElementsByClassName("tag");
	var i;

	for (i = 0; i < toggler.length; i++) {
	  toggler[i].addEventListener("click", function() {
	    this.parentElement.querySelector(".in_tag").classList.toggle("in_tag_active")
	    this.classList.toggle("tag-down")
	  })
	} 


