Feature: Editing

    Scenario: Find detail view at consistent url
        Given that I want to see detail for post 1
        When I enter the url /detail/1
        Then I see the detail page and the content of that post

    Scenario: Edit view
        Given that I want to edit post 1
        When I enter the url /editview/1
        Then I can see the new edit page and edit the entry

    Scenario: Add Markdown to a post
        Given that I use markdown syntax in my post
        When I view the markdown post
        Then markdown in the post will be rendered properly

    Scenario: Add code blocks to a post
        Given that I use backticks to denote a code block in my post
        When I view the color post
        Then the code in that block will be colorized
