{
    'name': 'Project Extension',
    'version': '19.0.1.0.0',
    'category': 'Project',
    'summary': 'Adds team, category, sub-category and task key to projects',
    'author': 'NCP',
    'license': 'LGPL-3',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_team.xml',
        'views/project_category.xml',
        'views/project_project.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': False,
}
