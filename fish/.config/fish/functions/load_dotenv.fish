function load_dotenv
    set -l file .env
    if test (count $argv) -gt 0
        set file $argv[1]
    end

    test -f "$file"; or return 1

    while read -l line
        set line (string trim -- "$line")

        # skip empty lines and comments
        string match -qr '^(#|$)' -- "$line"; and continue

        # skip malformed line
        string match -q '*=*' -- "$line"; or continue

        set -l parts (string split -m 1 '=' -- "$line")
        set -l key (string trim -- "$parts[1]")
        set -l value ""

        if set -q parts[2]
            set value (string trim -- "$parts[2]")
        end

        # strip surrounding simple quote
        set value (string trim --chars='"' -- "$value")
        set value (string trim --chars="'" -- "$value")

        # only allow valid env var name
        string match -qr '^[A-Za-z_][A-Za-z0-9_]*$' -- "$key"; or continue

        set -gx -- "$key" "$value"
    end <"$file"
end
