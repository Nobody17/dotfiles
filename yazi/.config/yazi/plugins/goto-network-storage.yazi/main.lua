-- Goes to the network storage of this machine.
--
-- macOS: the Nextcloud folder of the desktop client. Its name holds the
--        server and the account name, so this plugin looks for a folder that
--        starts with "Nextcloud" instead of one fixed path.
-- Linux: the mount point of the nas.
--
-- The plugin takes the first target that exists, so the same keymap works on
-- both platforms.

local NEXTCLOUD_PARENT_FOLDER = "/Library/CloudStorage"
local NEXTCLOUD_FOLDER_PREFIX = "Nextcloud"
local NAS_MOUNT_POINT = "/mnt/nas-hdd"

local function is_directory(path)
	local characteristics = fs.cha(Url(path))
	return characteristics ~= nil and characteristics.is_dir
end

-- Returns the path of the Nextcloud folder, or nil if this machine has none.
local function find_nextcloud_folder()
	local home = os.getenv("HOME")
	if home == nil then
		return nil
	end

	local parent_folder = home .. NEXTCLOUD_PARENT_FOLDER
	if not is_directory(parent_folder) then
		return nil
	end

	local entries = fs.read_dir(Url(parent_folder), { limit = 1000 })
	if entries == nil then
		return nil
	end

	for _, entry in ipairs(entries) do
		local path = tostring(entry.url)
		if entry.cha.is_dir and path:match("/" .. NEXTCLOUD_FOLDER_PREFIX .. "[^/]*$") then
			return path
		end
	end
	return nil
end

local function find_target()
	local nextcloud_folder = find_nextcloud_folder()
	if nextcloud_folder ~= nil then
		return nextcloud_folder
	end
	if is_directory(NAS_MOUNT_POINT) then
		return NAS_MOUNT_POINT
	end
	return nil
end

return {
	entry = function()
		local target = find_target()
		if target == nil then
			ya.notify({
				title = "Network storage",
				content = "This machine has no Nextcloud folder and no nas mount.",
				level = "warn",
				timeout = 4,
			})
			return
		end
		ya.emit("cd", { Url(target) })
	end,
}
