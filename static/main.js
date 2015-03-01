$(document).ready(function () {
  $('.add_entry').on('submit', function(event){
      event.preventDefault();
      add_post();
    });
});


function add_post() {
    var title = $('#title').val();
    var text = $('#text').val();
    $.ajax({
      url: '/new',
      type: 'POST',
      dataType: 'json',
      data: {'title': title, 'text': text},
      success: success
    });
}

function open_edit() {
    var id = $('.entry').attr('id').split("entry")[1];
    $.ajax({
      url: '/edit',
      type: 'GET',
      dataType: 'json',
      data: {'id': id},
      success: open_edit_success,
    });
}

function edit_post() {
    var title = $('#title').val();
    var text = $('#text').val();
    var split_path = window.location.pathname.split("/");
    var id = split_path[split_path.length-1];
    $.ajax({
      url: '/edit',
      type: 'POST',
      dataType: 'json',
      data: {'title': title, 'text': text, 'id': id},
      success: edit_success
    });
}

function success(entry){
    $('.add_entry').trigger('reset');

    var template = '<article class="entry" id="entry{{id}}">'+
                      '<h3 class="entryTitle"><a href= "/detail/{{id}}">{{title}}</a></h3>'+
                      '<p class="dateline">{{created}}'+
                      '<div class="entry_body">{{{text}}}</div>'+
                    '</article>';

    var html = Mustache.to_html(template, entry);
    $('#entriesTitle').after(html);
}

function edit_success(entry){
    var template = '<article class="entry" id="entry{{id}}">'+
                      '<h3 class="entryTitle"><a href= "/detail/{{id}}">{{title}}</a></h3>'+
                      '<p class="dateline">{{created}}'+
                      '<div class="entry_body">{{{text}}}</div>'+
                    '</article>';

    var html = Mustache.to_html(template, entry);
    $('#entryContent').html(html);
    $('#editTwitter').toggle();
}

function open_edit_success(entry){
  var template = '<aside><form action="{{ request.route_url("edit", id=entry.id) }}" method="POST" class="edit_entry">'+
                 '<div class="field"><label for="title">Title</label>'+
                 '<input type="text" value="{{title}}" size="30" name="title" id="title"/></div>'+
                 '<div class="field"><label for="text">Text</label>'+
                 '<textarea name="text" id="text" rows="5" cols="80">{{text}}</textarea></div>'+
                 '<div class="control_row"><input type="submit" value="Share" name="Share"/></div></form></aside>';

  var html = Mustache.to_html(template, entry);
  $('#editTwitter').toggle();
  $('#entryContent').html(html);
  $('.edit_entry').on('submit', function(event){
      event.preventDefault();
      edit_post();
  });
}





