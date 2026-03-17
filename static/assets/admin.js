async function loadSkills() {
  const r = await fetch("/api/skills/");
  const data = await r.json();

  let html = "";

  data.forEach(s => {
    html += `
      <tr>
        <td>${s.name}</td>
      </tr>
    `;
  });

  document.getElementById("skills").innerHTML = html;
}

loadSkills();