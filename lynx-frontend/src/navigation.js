function showHome() {
    document.getElementById('homeView').classList.add('active');
    document.getElementById('projectView').classList.remove('active');
    document.getElementById('tzView').classList.remove('active');
    document.getElementById('dataView').classList.remove('active');
    document.getElementById('breadcrumb').innerHTML = '<span class="link" onclick="goHome()">Проекты</span>';
    document.getElementById('projectQuickSelect').style.display = 'none';
    document.getElementById('btnNewProject').style.display = '';
    window.loadProjects();
}

function showProject(projectId) {
    window.currentProjectId = projectId;
    document.getElementById('homeView').classList.remove('active');
    document.getElementById('projectView').classList.add('active');

    const p = window.projects.find(x => x.id === projectId);
    document.getElementById('breadcrumb').innerHTML = `
        <span class="link" onclick="goHome()">Проекты</span>
        <span>/</span>
        <span class="current">${p ? p.name : '...'}</span>
        <button class="btn-delete-project" onclick="window.deleteProject('${projectId}')" title="Удалить проект">✕</button>
    `;

    const qs = document.getElementById('projectQuickSelect');
    qs.style.display = '';
    qs.value = projectId;

    document.getElementById('btnNewProject').style.display = 'none';

    window.loadProjectDetail(projectId);
    window.loadModels(projectId);
}

window.showHome = showHome;
window.showProject = showProject;
window.goHome = function() {
    window.currentProjectId = null;
    window.selectedModelId = null;
    showHome();
};

window.onQuickSelectProject = function(value) {
    if (value) showProject(value);
};
