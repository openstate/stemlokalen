from flask import render_template, request, redirect, url_for, flash
from flask_login import (
    UserMixin, login_required, login_user, logout_user, current_user
)
from app import app, db
from app.forms import (
    ResetPasswordRequestForm, ResetPasswordForm, LoginForm, EditForm,
    PubliceerForm
)
from app.email import send_password_reset_email
from app.models import User, ckan


field_order = [
    'Nummer stembureau',
    'Naam stembureau',
    'Gebruikersdoel het gebouw',
    'Website locatie',
    'BAG referentienummer',
    'Extra adresaanduiding',
    'Longitude',
    'Latitude',
    'Districtcode',
    'Openingstijden',
    'Mindervaliden toegankelijk',
    'Invalidenparkeerplaatsen',
    'Akoestiek',
    'Mindervalide toilet aanwezig',
    'Kieskring ID',
    'Hoofdstembureau',
    'Contactgegevens',
    'Beschikbaarheid'
]


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/over-deze-website")
def over_deze_website():
    return render_template('over-deze-website.html')


@app.route("/dataset")
def dataset():
    return render_template('dataset.html')


@app.route("/gemeente-reset-wachtwoord-verzoek", methods=['GET', 'POST'])
def gemeente_reset_wachtwoord_verzoek():
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash(
            'Er is een e-mail verzonden met instructies om het wachtwoord te '
            'veranderen'
        )
        return redirect(url_for('gemeente_login'))
    return render_template('gemeente-reset-wachtwoord-verzoek.html', form=form)


@app.route("/gemeente-reset-wachtwoord/<token>", methods=['GET', 'POST'])
def gemeente_reset_wachtwoord(token):
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.Wachtwoord.data)
        db.session.commit()
        flash('Uw wachtwoord is aangepast')
        return redirect(url_for('gemeente_login'))
    return render_template('gemeente-reset-wachtwoord.html', form=form)


@app.route("/gemeente-login", methods=['GET', 'POST'])
def gemeente_login():
    if current_user.is_authenticated:
        return redirect(url_for('gemeente_verkiezing_overzicht'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.Wachtwoord.data):
            flash('Fout e-mailadres of wachtwoord')
            return(redirect(url_for('gemeente_login')))
        login_user(user)
        return redirect(url_for('gemeente_verkiezing_overzicht'))
    return render_template('gemeente-login.html', form=form)


@app.route("/gemeente-logout")
@login_required
def gemeente_logout():
    logout_user()
    return redirect(url_for('index'))


@app.route("/gemeente-verkiezing-overzicht")
@login_required
def gemeente_verkiezing_overzicht():
    return render_template(
        'gemeente-verkiezing-overzicht.html',
        elections=ckan.elections
    )


@app.route(
    "/gemeente-stemlokalen-dashboard/<verkiezing>",
    methods=['GET', 'POST']
)
@login_required
def gemeente_stemlokalen_dashboard(verkiezing):
    publish_records = ckan.get_records(
        ckan.elections[verkiezing]['publish_resource']
    )
    draft_records = ckan.get_records(
        ckan.elections[verkiezing]['draft_resource']
    )

    publish_records = [
        record for record in publish_records['records']
        if record['CBS gemeentecode'] == current_user.gemeente_code
    ]
    draft_records = [
        record for record in draft_records['records']
        if record['CBS gemeentecode'] == current_user.gemeente_code
    ]

    return render_template(
        'gemeente-stemlokalen-dashboard.html',
        verkiezing=verkiezing,
        total_publish_records=len(publish_records),
        total_draft_records=len(draft_records)
    )


@app.route("/gemeente-stemlokalen-overzicht/<verkiezing>", methods=['GET', 'POST'])
@login_required
def gemeente_stemlokalen_overzicht(verkiezing):
    draft_records = ckan.get_records(
        ckan.elections[verkiezing]['draft_resource']
    )

    # Find the current largest primary_key value in order to create a
    # new primary_key value when the user wants to add a new stembureau
    largest_primary_key = 0
    for record in draft_records['records']:
        if record['primary_key'] > largest_primary_key:
            largest_primary_key = record['primary_key']

    draft_records = [
        record for record in draft_records['records']
        if record['CBS gemeentecode'] == current_user.gemeente_code
    ]

    _remove_id(draft_records)

    form = PubliceerForm()

    if form.validate_on_submit():
        if form.submit.data:
            ckan.publish(
                verkiezing, draft_records
            )
            flash('Stembureaus gepubliceerd')

    publish_records = ckan.get_records(
        ckan.elections[verkiezing]['publish_resource']
    )
    publish_records = [
        record for record in publish_records['records']
        if record['CBS gemeentecode'] == current_user.gemeente_code
    ]
    _remove_id(publish_records)

    # Check whether draft_records differs from publish_records in order
    # to disable or enable the 'Publiceer' button
    show_form = False
    if draft_records != publish_records:
        show_form = True

    return render_template(
        'gemeente-stemlokalen-overzicht.html',
        verkiezing=verkiezing,
        draft_records=draft_records,
        field_order=field_order,
        form=form,
        show_form=show_form,
        new_primary_key=largest_primary_key + 1
    )


@app.route("/gemeente-stemlokalen-edit/<verkiezing>/<stemlokaal_id>", methods=['GET', 'POST'])
@login_required
def gemeente_stemlokalen_edit(verkiezing, stemlokaal_id):
    draft_records = ckan.get_records(
        ckan.elections[verkiezing]['draft_resource']
    )

    draft_records = [
        record for record in draft_records['records']
        if record['CBS gemeentecode'] == current_user.gemeente_code
    ]

    # Initialize the form with the data already available in the draft
    init_record = {}
    for record in draft_records:
        if record['primary_key'] == int(stemlokaal_id):
            init_record = {
                'nummer_stembureau': record['Nummer stembureau'],
                'naam_stembureau': record['Naam stembureau'],
                'gebruikersdoel_het_gebouw': record['Gebruikersdoel het gebouw'],
                'website_locatie': record['Website locatie'],
                'bag_referentienummer': record['BAG referentienummer'],
                'extra_adresaanduiding': record['Extra adresaanduiding'],
                'longitude': record['Longitude'],
                'latitude': record['Latitude'],
                'districtcode': record['Districtcode'],
                'openingstijden': record['Openingstijden'],
                'mindervaliden_toegankelijk': record['Mindervaliden toegankelijk'],
                'invalidenparkeerplaatsen': record['Invalidenparkeerplaatsen'],
                'akoestiek': record['Akoestiek'],
                'mindervalide_toilet_aanwezig': record[
                    'Mindervalide toilet aanwezig'
                ],
                'kieskring_id': record['Kieskring ID'],
                'hoofdstembureau': record['Hoofdstembureau'],
                'contactgegevens': record['Contactgegevens'],
                'beschikbaarheid': record['Beschikbaarheid']
            }

    form = EditForm(**init_record)

    # When the user clicked the 'Annuleren' button go back to the
    # overzicht page without doing anything
    if form.submit_annuleren.data:
        flash('Bewerking geannuleerd')
        return redirect(
            url_for(
                'gemeente_stemlokalen_overzicht',
                verkiezing=verkiezing
            )
        )

    # When the user clicked the 'Verwijderen' button delete the
    # stembureau from the draft_resource
    if form.submit_verwijderen.data:
        ckan.delete_records(
            ckan.elections[verkiezing]['draft_resource'],
            {'primary_key': stemlokaal_id}
        )
        flash('Stembureau verwijderd')
        return redirect(
            url_for(
                'gemeente_stemlokalen_overzicht',
                verkiezing=verkiezing
            )
        )

    if form.validate_on_submit():
        record = _create_record(form, stemlokaal_id, current_user)
        ckan.save_records(
            ckan.elections[verkiezing]['draft_resource'],
            records=[record]
        )
        flash('Stembureau opgeslagen')
        return redirect(
            url_for(
                'gemeente_stemlokalen_overzicht',
                verkiezing=verkiezing
            )
        )

    return render_template(
        'gemeente-stemlokalen-edit.html',
        verkiezing=verkiezing,
        form=form
    )

def _create_record(form, stemlokaal_id, current_user):
    record = {
        'primary_key': stemlokaal_id,
        'Gemeente': current_user.gemeente_naam,
        'CBS gemeentecode': current_user.gemeente_code
    }

    for f in form:
        if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
            record[f.label.text] = f.data

    return record

# Remove '_id' as CKAN doesn't accept this field in upsert when we
# want to publish and '_id' is almost never the same in
# publish_records and draft_records so we need to remove it in order
# to compare them
def _remove_id(records):
    for record in records:
        del record['_id']


if __name__ == "__main__":
    app.run(threaded=True)
